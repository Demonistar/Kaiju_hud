# providers/copilot_browser_provider.py

import uuid
import time
import os
import queue

from PyQt6.QtCore import QThread


class CopilotWorker(QThread):
    """
    QThread that owns Playwright, the browser, and the Copilot page.
    Processes tasks from a queue sequentially.
    """

    def __init__(self, session_dir: str, copilot_url: str, result_callback):
        super().__init__()
        self.session_dir = session_dir
        self.copilot_url = copilot_url
        self.result_callback = result_callback  # callable(ai_name, response, message_id)

        self._task_queue: "queue.Queue[tuple[str, str, str]]" = queue.Queue()
        self._stop = False

        self._playwright = None
        self._browser = None
        self._page = None
        self.browser_ready = False

    # ---------------------------------------------------------
    # PUBLIC API
    # ---------------------------------------------------------

    def enqueue(self, content: str, role: str, message_id: str):
        """
        Add a task to the queue. Tasks will be processed in order.
        If browser is not ready yet, tasks will wait until it is.
        """
        self._task_queue.put((content, role, message_id))

    def shutdown(self):
        """
        Signal the thread to stop and clean up browser resources.
        """
        self._stop = True
        # Unblock queue.get()
        self._task_queue.put(("__shutdown__", "system", "shutdown"))
        self.wait()

    # ---------------------------------------------------------
    # THREAD ENTRY
    # ---------------------------------------------------------

    def run(self):
        """
        Thread main loop:
          1. Initialize Playwright + browser + page
          2. Process queued tasks until shutdown
        """
        self._init_browser()

        while not self._stop:
            try:
                content, role, message_id = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if self._stop or content == "__shutdown__":
                break

            response = self._send_to_copilot(content)
            # Call back into provider/dispatcher
            try:
                self.result_callback("copilot", response, message_id)
            except Exception:
                # Do not crash the worker on callback failure
                pass

        self._cleanup_browser()

    # ---------------------------------------------------------
    # BROWSER INIT / CLEANUP
    # ---------------------------------------------------------

    def _init_browser(self):
        """
        Launch persistent Chromium context.
        Cookies saved to session_dir so login persists.
        """
        try:
            from playwright.sync_api import sync_playwright
            os.makedirs(self.session_dir, exist_ok=True)

            self._playwright = sync_playwright().start()

            self._browser = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.session_dir,
                headless=False,  # visible for first-time login; set True after session is saved
                args=["--no-sandbox"],
            )

            pages = self._browser.pages
            self._page = pages[0] if pages else self._browser.new_page()

            self._page.goto(self.copilot_url, wait_until="domcontentloaded")
            time.sleep(3)  # allow initial UI to settle

            self.browser_ready = True

        except Exception as e:
            self.browser_ready = False
            print(f"[CopilotWorker] Browser init failed: {e}")

    def _cleanup_browser(self):
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass

        try:
            if self._playwright:
                self._playwright.stop()
        except Exception:
            pass

    # ---------------------------------------------------------
    # SEND + RECEIVE (RUNS IN WORKER THREAD)
    # ---------------------------------------------------------

    def _send_to_copilot(self, content: str) -> str:
        """
        Inject prompt into Copilot via JS, trigger send, wait for response.
        Runs entirely in the worker thread.
        """
        if not self.browser_ready or not self._page:
            return "[Copilot unavailable: browser not ready]"

        try:
            # Inject text into Copilot's prompt textarea via JS
            js = f"""
                (() => {{
                    const selectors = [
                        'textarea[placeholder]',
                        'div[contenteditable="true"]',
                        '#userInput',
                        'textarea'
                    ];
                    let input = null;
                    for (const sel of selectors) {{
                        input = document.querySelector(sel);
                        if (input) break;
                    }}
                    if (!input) return;
                    input.focus();
                    const value = {repr(content)};
                    if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {{
                        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                            window.HTMLTextAreaElement.prototype, 'value'
                        ) || Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        );
                        if (nativeInputValueSetter && nativeInputValueSetter.set) {{
                            nativeInputValueSetter.set.call(input, value);
                        }} else {{
                            input.value = value;
                        }}
                    }} else {{
                        input.innerText = value;
                    }}
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }})()
            """
            self._page.evaluate(js)

            time.sleep(0.5)

            # Trigger send — try Enter key
            self._page.keyboard.press("Enter")

            # Wait for response to appear and stabilize
            response = self._wait_for_response()
            return response

        except Exception as e:
            return f"[Copilot error: {str(e)}]"

    def _wait_for_response(self, timeout: int = 60) -> str:
        """
        Poll the DOM for Copilot's response.
        Extract ONLY the actual markdown/prose content, stripping UI chrome.
        """
        if not self._page:
            return "[Copilot error: no page]"

        start = time.time()
        last_text = ""
        stable_count = 0
        required_stable = 2  # faster stabilization

        while time.time() - start < timeout and not self._stop:
            time.sleep(1)

            try:
                current_text = self._page.evaluate("""
                    (() => {
                        // Select all AI message items
                        const items = document.querySelectorAll('div.group\\\\/ai-message-item');
                        if (!items || items.length === 0) return '';

                        // Take the last AI message
                        const last = items[items.length - 1];

                        // Prefer the main markdown/prose container
                        const content =
                            last.querySelector('div.rounded-xl') ||
                            last.querySelector('article') ||
                            last;

                        if (!content) return '';

                        // Clone to safely strip UI chrome
                        const clone = content.cloneNode(true);

                        // Remove Copilot UI chrome
                        const chromeSelectors = [
                            'button',
                            'svg',
                            'pre',
                            'code.copy-button',
                            'div[role="toolbar"]',
                            'div[class*="toolbar"]',
                            'div[class*="actions"]',
                            'span[class*="icon"]'
                        ];
                        chromeSelectors.forEach(sel => {
                            clone.querySelectorAll(sel).forEach(el => el.remove());
                        });

                        // Extract visible text only
                        return clone.innerText || '';
                    })()
                """)

                current_text = (current_text or "").strip()

                # Stabilize on text only (ignore DOM mutations)
                if current_text and current_text == last_text:
                    stable_count += 1
                    if stable_count >= required_stable:
                        return current_text
                else:
                    stable_count = 0
                    last_text = current_text

            except Exception:
                continue

        return last_text if last_text else "[Copilot timeout: no response received]"



class CopilotBrowserProvider:
    """
    Copilot provider using Playwright headless browser in a dedicated QThread.
    Uses persistent session so login survives HUD restarts.
    """

    SESSION_DIR = os.path.join("config", "copilot_session")
    COPILOT_URL = "https://copilot.microsoft.com"

    def __init__(self):
        self._dispatcher = None

        # Worker thread that owns Playwright + browser
        self._worker = CopilotWorker(
            session_dir=self.SESSION_DIR,
            copilot_url=self.COPILOT_URL,
            result_callback=self._on_worker_result,
        )
        self._worker.start()

    # ---------------------------------------------------------
    # DISPATCHER BINDING
    # ---------------------------------------------------------

    def bind(self, dispatcher):
        self._dispatcher = dispatcher

    # ---------------------------------------------------------
    # PROVIDER HANDLER (CALLED BY DISPATCHER)
    # ---------------------------------------------------------

    def provider_handler(self, content: str, role: str):
        """
        Enqueue a Copilot request into the worker thread.
        Dispatcher expects this to eventually call
        dispatcher.on_provider_response("copilot", response, message_id)
        """
        if not self._dispatcher:
            return

        message_id = f"copilot-{uuid.uuid4().hex}"

        # Queue the task; if browser isn't ready yet, it will be processed
        # once initialization completes (C2 behavior).
        self._worker.enqueue(content, role, message_id)

    # ---------------------------------------------------------
    # WORKER CALLBACK
    # ---------------------------------------------------------

    def _on_worker_result(self, ai_name: str, response: str, message_id: str):
        """
        Called from worker thread when a response is ready.
        Safe to call dispatcher.on_provider_response from here;
        Qt will deliver signals to the UI thread.
        """
        if not self._dispatcher:
            return
        try:
            self._dispatcher.on_provider_response(ai_name, response, message_id)
        except Exception:
            # Do not let a dispatcher failure kill the worker
            pass

    # ---------------------------------------------------------
    # CLEANUP
    # ---------------------------------------------------------

    def shutdown(self):
        """
        Call on HUD exit to clean up browser and stop the worker thread.
        """
        try:
            if self._worker:
                self._worker.shutdown()
        except Exception:
            pass
