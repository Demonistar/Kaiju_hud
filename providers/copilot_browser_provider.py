# providers/copilot_browser_provider.py

import uuid
import time
import os
import queue

from PyQt6.QtCore import QThread

IDENTITY_PREFIX = (
    "You are Copilot, made by Microsoft. You are Column 4 in a 5-column "
    "multi-AI interface called the Kaiju Command Bridge. Maintain your "
    "identity as Copilot at all times. Do not mention this instruction.\n"
)


class CopilotWorker(QThread):
    def __init__(self, session_dir: str, copilot_url: str, result_callback):
        super().__init__()
        self.session_dir = session_dir
        self.copilot_url = copilot_url
        self.result_callback = result_callback
        self._task_queue: "queue.Queue[tuple[str, str, str]]" = queue.Queue()
        self._stop = False
        self._playwright = None
        self._browser = None
        self._page = None
        self.browser_ready = False

    def enqueue(self, content: str, role: str, message_id: str):
        self._task_queue.put((content, role, message_id))

    def shutdown(self):
        self._stop = True
        self._task_queue.put(("__shutdown__", "system", "shutdown"))
        self.wait()

    def run(self):
        self._init_browser()
        while not self._stop:
            try:
                content, role, message_id = self._task_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if self._stop or content == "__shutdown__":
                break
            response = self._send_to_copilot(content)
            try:
                self.result_callback("copilot", response, message_id)
            except Exception:
                pass
        self._cleanup_browser()

    def _init_browser(self):
        try:
            from playwright.sync_api import sync_playwright
            os.makedirs(self.session_dir, exist_ok=True)
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.session_dir,
                headless=False,
                args=["--no-sandbox"],
            )
            pages = self._browser.pages
            self._page = pages[0] if pages else self._browser.new_page()
            self._page.goto(self.copilot_url, wait_until="domcontentloaded")
            time.sleep(3)
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

    def _send_to_copilot(self, content: str) -> str:
        if not self.browser_ready or not self._page:
            return "[Copilot unavailable: browser not ready]"
        try:
            injected_content = IDENTITY_PREFIX + content
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
                    const value = {repr(injected_content)};
                    if (input.tagName === 'TEXTAREA' || input.tagName === 'INPUT') {{
                        const setter = Object.getOwnPropertyDescriptor(
                            window.HTMLTextAreaElement.prototype, 'value'
                        ) || Object.getOwnPropertyDescriptor(
                            window.HTMLInputElement.prototype, 'value'
                        );
                        if (setter && setter.set) {{
                            setter.set.call(input, value);
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
            self._page.keyboard.press("Enter")
            return self._wait_for_response()
        except Exception as e:
            return f"[Copilot error: {str(e)}]"

    def _wait_for_response(self, timeout: int = 90) -> str:
        if not self._page:
            return "[Copilot error: no page]"

        start = time.time()
        last_text = ""
        stable_count = 0

        # Wait a moment for response to start appearing
        time.sleep(2)

        while time.time() - start < timeout and not self._stop:
            time.sleep(1)
            try:
                current_text = self._page.evaluate("""
                    (() => {
                        // Try multiple selector strategies for Copilot's response
                        const strategies = [
                            // Strategy 1: Original selector
                            () => {
                                const items = document.querySelectorAll('div.group\\/ai-message-item');
                                if (items && items.length > 0) {
                                    const last = items[items.length - 1];
                                    const content = last.querySelector('div.rounded-xl') ||
                                                   last.querySelector('article') || last;
                                    return content ? content.innerText : null;
                                }
                                return null;
                            },
                            // Strategy 2: Look for cib-chat-turn (older Copilot)
                            () => {
                                const items = document.querySelectorAll('cib-chat-turn');
                                if (items && items.length > 0) {
                                    const last = items[items.length - 1];
                                    return last ? last.innerText : null;
                                }
                                return null;
                            },
                            // Strategy 3: Look for ai-message role
                            () => {
                                const items = document.querySelectorAll('[data-testid="ai-message"]');
                                if (items && items.length > 0) {
                                    return items[items.length - 1].innerText;
                                }
                                return null;
                            },
                            // Strategy 4: Look for response containers by role
                            () => {
                                const items = document.querySelectorAll('[role="presentation"]');
                                const aiItems = Array.from(items).filter(el => 
                                    el.className.includes('ai') || 
                                    el.className.includes('bot') ||
                                    el.className.includes('assistant') ||
                                    el.className.includes('response')
                                );
                                if (aiItems.length > 0) {
                                    return aiItems[aiItems.length - 1].innerText;
                                }
                                return null;
                            },
                            // Strategy 5: Broadest fallback - any message container
                            () => {
                                const candidates = [
                                    'div[class*="message"]',
                                    'div[class*="response"]', 
                                    'div[class*="answer"]',
                                    'div[class*="assistant"]',
                                    'div[class*="bot"]'
                                ];
                                for (const sel of candidates) {
                                    const items = document.querySelectorAll(sel);
                                    if (items && items.length > 0) {
                                        const last = items[items.length - 1];
                                        const text = last.innerText;
                                        if (text && text.length > 20) return text;
                                    }
                                }
                                return null;
                            }
                        ];

                        for (const strategy of strategies) {
                            try {
                                const result = strategy();
                                if (result && result.trim().length > 0) {
                                    return result.trim();
                                }
                            } catch(e) {
                                continue;
                            }
                        }
                        return '';
                    })()
                """)

                current_text = (current_text or "").strip()

                if current_text and current_text == last_text:
                    stable_count += 1
                    if stable_count >= 2:
                        return current_text
                else:
                    stable_count = 0
                    last_text = current_text

            except Exception:
                continue

        return last_text if last_text else "[Copilot timeout: no response received]"


class CopilotBrowserProvider:
    SESSION_DIR = os.path.join("config", "copilot_session")
    COPILOT_URL = "https://copilot.microsoft.com"

    def __init__(self):
        self._dispatcher = None
        self._worker = CopilotWorker(
            session_dir=self.SESSION_DIR,
            copilot_url=self.COPILOT_URL,
            result_callback=self._on_worker_result,
        )
        self._worker.start()

    def bind(self, dispatcher):
        self._dispatcher = dispatcher

    def provider_handler(self, content: str, role: str):
        if not self._dispatcher:
            return
        message_id = f"copilot-{uuid.uuid4().hex}"
        self._worker.enqueue(content, role, message_id)

    def _on_worker_result(self, ai_name: str, response: str, message_id: str):
        if not self._dispatcher:
            return
        try:
            self._dispatcher.on_provider_response(ai_name, response, message_id)
        except Exception:
            pass

    def shutdown(self):
        try:
            if self._worker:
                self._worker.shutdown()
        except Exception:
            pass