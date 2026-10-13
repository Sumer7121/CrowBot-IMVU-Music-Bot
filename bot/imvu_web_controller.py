from playwright.sync_api import sync_playwright





class IMVUWebController:

    """

    Controls the already-running dedicated IMVU Chrome session through

    Chrome DevTools Protocol (CDP).



    This controller does not read passwords, cookies, or session tokens.

    It attaches to Chrome at http://127.0.0.1:9222 and interacts only

    with the visible IMVU Web room UI.

    """



    def __init__(self, debugging_url="http://127.0.0.1:9222"):

        self.debugging_url = debugging_url

        self.playwright = None

        self.browser = None

        self.context = None

        self.page = None



        # Live-chat state. data-chat-entry is IMVU's per-entry identifier.

        self.seen_chat_entries = set()



    # =========================================================

    # CONNECTION

    # =========================================================



    def connect(self):

        if self.browser:

            return True



        try:

            self.playwright = sync_playwright().start()

            self.browser = self.playwright.chromium.connect_over_cdp(

                self.debugging_url

            )



            if not self.browser.contexts:

                raise RuntimeError(

                    "Chrome was found, but no browser context is available."

                )



            self.context = self.browser.contexts[0]

            return True



        except Exception:

            self.disconnect()

            raise



    def find_imvu_room(self):

        if not self.context:

            raise RuntimeError(

                "The controller is not connected to Chrome."

            )



        for page in self.context.pages:

            try:

                url = page.url or ""

                if "imvu.com/next/chat/room-" in url.lower():

                    self.page = page

                    return page

            except Exception:

                continue



        self.page = None

        return None



    def get_room_url(self):

        if not self.page:

            return ""

        return self.page.url



    def get_page_title(self):

        if not self.page:

            return ""

        try:

            return self.page.title()

        except Exception:

            return ""



    # =========================================================

    # ROOM JOINING

    # =========================================================



    def join_button(self):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        primary = self.page.locator("button.join-cta")

        if primary.count() > 0:

            return primary



        return self.page.get_by_role(

            "button",

            name="JOIN",

            exact=True,

        )



    def join_button_visible(self):

        if not self.page:

            return False



        try:

            button = self.join_button()

            return (

                button.count() > 0

                and button.first.is_visible()

            )

        except Exception:

            return False



    def is_joined(self):

        if not self.page:

            return False



        try:

            return not self.join_button_visible()

        except Exception:

            return False



    def ensure_joined(self, timeout_ms=30000):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        self.page.wait_for_load_state(

            "domcontentloaded",

            timeout=timeout_ms,

        )

        self.page.wait_for_timeout(1000)



        if not self.join_button_visible():

            # IMVU can retain a dead temporary radio URL from an earlier
            # session. Clear only its error modal before chat starts.
            self.dismiss_radio_stream_error()

            return {

                "joined": True,

                "clicked": False,

                "status": "already_joined",

                "room_url": self.get_room_url(),

            }



        button = self.join_button().first



        try:

            button.scroll_into_view_if_needed()

        except Exception:

            pass



        button.click(timeout=timeout_ms)



        try:

            button.wait_for(

                state="hidden",

                timeout=timeout_ms,

            )

        except Exception:

            if self.join_button_visible():

                raise RuntimeError(

                    "JOIN was clicked, but IMVU still shows the "

                    "JOIN control. The room may not have finished "

                    "joining or IMVU may have displayed a prompt."

                )



        self.page.wait_for_timeout(1500)

        # Dismiss the error caused by IMVU retrying a persisted dead radio URL.
        self.dismiss_radio_stream_error()



        if self.join_button_visible():

            raise RuntimeError(

                "IMVU still shows the JOIN control after the "

                "automatic join attempt."

            )



        return {

            "joined": True,

            "clicked": True,

            "status": "joined",

            "room_url": self.get_room_url(),

        }



    # =========================================================
    # STALE RADIO ERROR DIALOG
    # =========================================================

    def radio_stream_error_dialog_visible(self):
        """Return True only when IMVU's RADIO STREAM ERROR modal is visible."""
        if not self.page:
            return False

        try:
            title = self.page.get_by_text(
                "RADIO STREAM ERROR",
                exact=True,
            )
            return title.count() > 0 and title.first.is_visible()
        except Exception:
            return False

    def dismiss_radio_stream_error(self, timeout_ms=3000):
        """
        Dismiss the stale persisted-radio error that IMVU can show on room join.

        This only acts when RADIO STREAM ERROR is visible. It does not change
        the stored station URL and does not toggle Radio Streaming.
        """
        if not self.page or not self.radio_stream_error_dialog_visible():
            return False

        try:
            dismiss = self.page.get_by_role(
                "button",
                name="DISMISS",
                exact=True,
            )

            if dismiss.count() == 0:
                dismiss = self.page.get_by_text(
                    "DISMISS",
                    exact=True,
                )

            if dismiss.count() == 0 or not dismiss.first.is_visible():
                return False

            dismiss.first.click(timeout=timeout_ms)

            elapsed = 0
            while elapsed < timeout_ms:
                if not self.radio_stream_error_dialog_visible():
                    self.page.wait_for_timeout(250)
                    return True

                self.page.wait_for_timeout(100)
                elapsed += 100

            return not self.radio_stream_error_dialog_visible()

        except Exception:
            return False


    # =========================================================

    # LIVE CHAT

    # =========================================================



    def chat_message_rows(self):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        return self.page.locator(

            '.cs2-msg[data-chat-body-kind="literal-text"]'

            '[data-chat-delivery="settled"]'

        )



    def get_visible_chat_messages(self, include_own=False):

        if not self.page:

            raise RuntimeError(
                "No IMVU room page has been selected."
            )

        # Extract all currently rendered chat rows inside the browser
        # in ONE Playwright/CDP round-trip.
        #
        # The old implementation queried each row and each attribute
        # separately through Playwright. With hundreds of rendered
        # messages that created hundreds/thousands of CDP calls on
        # every listener poll.
        #
        # Keep the same fields expected by the existing listener:
        # entry_id, user_id, timestamp, username, message, is_me.

        messages = self.page.locator(
            "[data-chat-entry]"
        ).evaluate_all(
            """
            (rows) => rows.map((row) => {

                const isMe =
                    row.classList.contains("is-me");

                const entryId =
                    (row.getAttribute("data-chat-entry") || "")
                    .trim();

                const userId =
                    (row.getAttribute("data-id") || "")
                    .trim();

                const timestamp =
                    (row.getAttribute("data-timestamp") || "")
                    .trim();

                const textParts =
                    Array.from(
                        row.querySelectorAll(".user-text")
                    )
                    .map((element) =>
                        (element.innerText || "").trim()
                    )
                    .filter(Boolean);

                const message =
                    textParts.join(String.fromCharCode(10)).trim();

                let username = "";

                const displayName =
                    row.querySelector(".display-name-text");

                if (displayName) {

                    username =
                        (displayName.innerText || "").trim();

                }

                if (!username) {

                    const image =
                        row.querySelector(
                            ".chat-row-profile img[alt]"
                        );

                    if (image) {

                        username =
                            (image.getAttribute("alt") || "")
                            .trim();

                    }

                }

                if (!username) {

                    username = "Unknown User";

                }

                return {
                    entry_id: entryId,
                    user_id: userId,
                    timestamp: timestamp,
                    username: username,
                    message: message,
                    is_me: isMe,
                };

            })
            """
        )

        if not include_own:

            messages = [
                message
                for message in messages
                if not message.get("is_me")
            ]

        return [
            message
            for message in messages
            if message.get("message")
        ]



    def prime_chat_listener(self):

        messages = self.get_visible_chat_messages(include_own=True)



        for message in messages:

            entry_id = message.get("entry_id")

            if entry_id:

                self.seen_chat_entries.add(entry_id)



        return len(self.seen_chat_entries)



    def get_new_chat_messages(self):

        messages = self.get_visible_chat_messages(include_own=True)

        new_messages = []



        for message in messages:

            entry_id = message.get("entry_id")



            if entry_id:

                signature = entry_id

            else:

                signature = "|".join(

                    [

                        message.get("user_id", ""),

                        message.get("timestamp", ""),

                        message.get("username", ""),

                        message.get("message", ""),

                    ]

                )



            if signature in self.seen_chat_entries:

                continue



            self.seen_chat_entries.add(signature)



            if message.get("is_me"):

                continue



            new_messages.append(message)



        return new_messages



    def wait_for_new_chat_messages(

        self,

        timeout_ms=500,

        poll_interval_ms=100,

    ):

        """

        Poll for new external messages.



        Opening IMVU Media can temporarily remove/hide the chat DOM.

        An empty chat DOM is therefore treated as a temporary UI state,

        not as a listener failure. Polling resumes automatically when

        the Media panel is closed and chat becomes available again.

        """

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        elapsed = 0



        while elapsed < timeout_ms:

            try:

                messages = self.get_new_chat_messages()

                if messages:

                    return messages

            except Exception:

                # IMVU can rebuild the room/chat DOM while Media opens

                # or closes. Keep the long-lived listener alive.

                pass



            wait_ms = min(

                poll_interval_ms,

                timeout_ms - elapsed,

            )



            if wait_ms <= 0:

                break



            try:

                self.page.wait_for_timeout(wait_ms)

            except Exception:

                break



            elapsed += wait_ms



        return []



    # =========================================================

    # OUTBOUND CHAT

    # =========================================================



    def chat_input(self):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        return self.page.locator(

            'textarea[placeholder="Say something..."]'

        )



    def chat_send_button(self):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        return self.page.locator("button.btn-send")



    def send_chat_message(self, message, timeout_ms=5000):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        message = str(message or "").strip()

        if not message:

            raise ValueError(

                "The IMVU chat message cannot be empty."

            )



        chat_input = self.chat_input()

        if chat_input.count() == 0:

            raise RuntimeError(

                "The IMVU chat textarea was not found."

            )



        chat_input = chat_input.first

        if not chat_input.is_visible():

            raise RuntimeError(

                "The IMVU chat textarea exists but is not visible."

            )



        send_button = self.chat_send_button()

        if send_button.count() == 0:

            raise RuntimeError(

                "The IMVU SEND button was not found."

            )



        send_button = send_button.first

        if not send_button.is_visible():

            raise RuntimeError(

                "The IMVU SEND button exists but is not visible."

            )



        chat_input.fill(message)

        self.page.wait_for_timeout(50)



        if send_button.is_disabled():

            raise RuntimeError(

                "The IMVU SEND button remained disabled after "

                "the message was entered."

            )



        send_button.click(timeout=timeout_ms)

        

        return True



    # =========================================================

    # MEDIA / RADIO STREAMING

    # =========================================================



    def media_button(self):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        return self.page.locator('li[data-nav="media-button"]')



    def radio_toggle(self):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        return self.page.locator("#enable-radio-toggle")



    def radio_url_input(self):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        # Prefer the verified stable ID.

        by_id = self.page.locator("#radio-station-input")

        if by_id.count() > 0:

            return by_id



        # Fallback retained for compatibility with older IMVU markup.

        return self.page.get_by_placeholder(

            "Enter the radio station URL"

        )



    def load_button(self):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        return self.page.get_by_role(

            "button",

            name="LOAD",

            exact=True,

        )



    def _radio_controls_are_visible_now(self):

        if not self.page:

            return False



        try:

            radio_input = self.radio_url_input()

            load_button = self.load_button()



            return (

                radio_input.count() > 0

                and radio_input.first.is_visible()

                and load_button.count() > 0

                and load_button.first.is_visible()

            )

        except Exception:

            return False



    def open_media_panel(self, timeout_ms=7000):

        """

        Open IMVU Media only when the radio controls are not already visible.

        """

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        if self._radio_controls_are_visible_now():

            return False



        button = self.media_button()

        if button.count() == 0:

            raise RuntimeError(

                "IMVU Media button was not found."

            )



        button = button.first

        if not button.is_visible():

            raise RuntimeError(

                "IMVU Media button exists but is not visible."

            )



        button.click(timeout=timeout_ms)



        # Wait for the Radio Streaming toggle/panel to appear.

        elapsed = 0

        while elapsed < timeout_ms:

            toggle = self.radio_toggle()



            if (

                toggle.count() > 0

                and toggle.first.is_visible()

            ):

                return True



            if self._radio_controls_are_visible_now():

                return True



            self.page.wait_for_timeout(200)

            elapsed += 200



        raise RuntimeError(

            "IMVU Media opened, but Radio Streaming controls "

            "did not appear."

        )



    def ensure_radio_streaming_on(self, timeout_ms=15000):
        """
        Open IMVU Media and guarantee that Radio Streaming is ON.

        Fresh rooms can take longer to create the URL/LOAD controls after
        the first toggle activation, so this method explicitly verifies the
        toggle and waits for the controls instead of assuming one click
        completed the transition.
        """
        if not self.page:
            raise RuntimeError(
                "No IMVU room page has been selected."
            )

        self.open_media_panel(
            timeout_ms=min(timeout_ms, 10000)
        )

        # A previously configured room may already expose both controls.
        if self._radio_controls_are_visible_now():
            return True

        toggle = self.radio_toggle()

        if toggle.count() == 0:
            raise RuntimeError(
                "IMVU Radio Streaming toggle was not found "
                "after opening Media."
            )

        toggle = toggle.first

        if not toggle.is_visible():
            raise RuntimeError(
                "IMVU Radio Streaming toggle exists but is not visible."
            )

        def toggle_is_checked():
            try:
                return bool(toggle.is_checked())
            except Exception:
                checked_attr = toggle.get_attribute("checked")
                aria_checked = (
                    toggle.get_attribute("aria-checked")
                    or ""
                ).lower()

                return (
                    checked_attr is not None
                    or aria_checked == "true"
                )

        # Never blindly toggle. Only click when it is actually OFF.
        if not toggle_is_checked():
            try:
                toggle.scroll_into_view_if_needed()
            except Exception:
                pass

            try:
                toggle.click(timeout=5000)
            except Exception:
                # Some fresh-room IMVU renders place a transient layer over
                # the checkbox. Force-click is a controlled fallback.
                toggle.click(
                    timeout=5000,
                    force=True,
                )

            self.page.wait_for_timeout(600)

        # Verify the switch becomes ON. If IMVU ignored the first click,
        # retry exactly once while it is still OFF.
        checked_wait = 0

        while checked_wait < 5000:
            if toggle_is_checked():
                break

            if self._radio_controls_are_visible_now():
                return True

            self.page.wait_for_timeout(200)
            checked_wait += 200

        if (
            not toggle_is_checked()
            and not self._radio_controls_are_visible_now()
        ):
            try:
                toggle.click(
                    timeout=5000,
                    force=True,
                )
                self.page.wait_for_timeout(700)
            except Exception as error:
                raise RuntimeError(
                    "IMVU Radio Streaming switch could not be enabled."
                ) from error

        # Fresh rooms can take several seconds to render these controls.
        elapsed = 0

        while elapsed < timeout_ms:
            if self._radio_controls_are_visible_now():
                return True

            # If IMVU rerendered the toggle, reacquire it.
            try:
                current_toggle = self.radio_toggle()

                if (
                    current_toggle.count() > 0
                    and current_toggle.first.is_visible()
                ):
                    current_toggle = current_toggle.first

                    try:
                        current_checked = (
                            current_toggle.is_checked()
                        )
                    except Exception:
                        current_checked = (
                            current_toggle.get_attribute(
                                "checked"
                            ) is not None
                            or (
                                current_toggle.get_attribute(
                                    "aria-checked"
                                )
                                or ""
                            ).lower() == "true"
                        )

                    if not current_checked and elapsed >= 3000:
                        current_toggle.click(
                            timeout=3000,
                            force=True,
                        )
            except Exception:
                pass

            self.page.wait_for_timeout(250)
            elapsed += 250

        raise RuntimeError(
            "Radio Streaming is enabled, but IMVU did not expose "
            "the station URL and LOAD controls within 15 seconds."
        )

    def chat_button(self):

        if not self.page:

            raise RuntimeError("No IMVU room page has been selected.")

        return self.page.locator('li[data-nav="chat-button"]')



    def restore_chat_panel(self, timeout_ms=5000):

        """Explicitly switch back to Chat after a radio update."""

        if not self.page:

            return False

        try:

            button = self.chat_button()

            if button.count() == 0:

                raise RuntimeError("IMVU Chat navigation button was not found.")

            button = button.first

            if not button.is_visible():

                raise RuntimeError("IMVU Chat navigation button exists but is not visible.")

            button.click(timeout=timeout_ms)

            elapsed = 0

            while elapsed < timeout_ms:

                try:

                    chat_input = self.chat_input()

                    if chat_input.count() > 0 and chat_input.first.is_visible():

                        self.page.wait_for_timeout(300)

                        return True

                except Exception:

                    pass

                self.page.wait_for_timeout(50)

                elapsed += 150

            return False

        except Exception:

            return False



    def close_media_panel(self, timeout_ms=5000):

        """Backward-compatible alias that explicitly restores Chat."""

        return self.restore_chat_panel(timeout_ms=timeout_ms)



    def radio_controls_visible(self):

        """

        Compatibility method used by the GUI radio worker.



        Older code only checked whether Media was already open, which forced

        the user to open Media manually. This version actively opens Media

        and enables Radio Streaming so the existing main_window pre-check

        succeeds without manual interaction.

        """

        if not self.page:

            return False



        try:

            self.ensure_radio_streaming_on()

            return self._radio_controls_are_visible_now()

        except Exception:

            return False



    def get_current_stream_url(self):

        try:

            if not self._radio_controls_are_visible_now():

                self.ensure_radio_streaming_on()



            radio_input = self.radio_url_input()

            if radio_input.count() == 0:

                return ""



            return radio_input.first.input_value()

        except Exception:

            return ""



    def set_stream_url(self, stream_url):

        """

        Enter the IMVU Radio Streaming URL using real keyboard events.



        Do not replace this with locator.fill(). The live IMVU field was

        verified to accept the URL reliably when it arrives as keyboard input.

        """

        stream_url = (stream_url or "").strip()



        if not stream_url:

            raise ValueError(

                "The stream URL cannot be empty."

            )



        if not stream_url.startswith("https://"):

            raise ValueError(

                "IMVU Radio Streaming requires an HTTPS stream URL."

            )



        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        if not self._radio_controls_are_visible_now():

            self.ensure_radio_streaming_on()



        radio_input = self.radio_url_input()



        if radio_input.count() == 0:

            raise RuntimeError(

                "The IMVU Radio Streaming URL field was not found."

            )



        radio_input = radio_input.first



        if not radio_input.is_visible():

            raise RuntimeError(

                "The IMVU Radio Streaming URL field exists "

                "but is not currently visible."

            )



        radio_input.scroll_into_view_if_needed()

        radio_input.click()



        # IMPORTANT: IMVU's controlled input needs real keyboard events.

        radio_input.press("Control+A")

        radio_input.press("Backspace")

        self.page.wait_for_timeout(50)

        radio_input.type(stream_url, delay=12)



        self.page.wait_for_timeout(500)



        actual_value = radio_input.input_value().strip()



        if actual_value != stream_url:

            raise RuntimeError(

                "IMVU did not accept the complete stream URL. "

                f"Expected {stream_url!r}, got {actual_value!r}."

            )



        return actual_value



    def click_load(self):

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        button = self.load_button()



        if button.count() == 0:

            raise RuntimeError(

                "The IMVU Radio Streaming LOAD button was not found."

            )



        button = button.first



        if not button.is_visible():

            raise RuntimeError(

                "The IMVU Radio Streaming LOAD button is not visible."

            )



        button.click()

        self.page.wait_for_timeout(500)

        return True



    def load_stream(self, stream_url):

        """

        Automatically perform the complete IMVU Radio Streaming workflow:



            Media -> Radio Streaming ON -> URL -> LOAD -> restore Chat



        Media is closed in finally so the room chat UI is restored even if

        entering/loading the stream raises an exception.

        """

        if not self.page:

            raise RuntimeError(

                "No IMVU room page has been selected."

            )



        opened_for_update = False



        try:

            if not self._radio_controls_are_visible_now():

                self.ensure_radio_streaming_on()

                opened_for_update = True



            previous_url = self.get_current_stream_url()



            self.set_stream_url(stream_url)

            self.click_load()



            return {

                "previous_url": previous_url,

                "new_url": stream_url,

                "loaded": True,

            }



        finally:

            # The chat listener depends on the room chat DOM. Restore that

            # view immediately after the short-lived radio operation.

            self.restore_chat_panel()



    # =========================================================

    # DISCONNECT

    # =========================================================



    def disconnect(self):

        """

        Detach Playwright from the existing Chrome session.

        Chrome itself is intentionally left running.

        """

        self.page = None

        self.context = None



        # Do not call browser.close(). This controller attaches

        # to an existing Chrome process and must not shut it down.

        self.browser = None



        if self.playwright:

            try:

                self.playwright.stop()

            except Exception:

                pass



        self.playwright = None





def main():

    """

    Standalone live-chat test.



    It attaches to the existing bot Chrome session, joins the room if

    necessary, ignores already-rendered history, then prints NEW messages

    from other users. It does not send chat messages and does not change

    Radio Streaming.

    """

    controller = IMVUWebController()



    print()

    print("IMVU Live Chat Listener Test")

    print("------------------------------------")

    print()



    try:

        controller.connect()

        print("Chrome connection: OK")



        room_page = controller.find_imvu_room()



        if not room_page:

            print("IMVU room tab: NOT FOUND")

            return



        print("IMVU room tab: FOUND")

        print()

        print("Room:")

        print(controller.get_room_url())

        print()



        result = controller.ensure_joined()



        if result.get("clicked"):

            print("Room join: SUCCESS")

        else:

            print("Room join: ALREADY JOINED")



        print()

        print("Starting live chat listener...")

        primed = controller.prime_chat_listener()

        print(f"Ignoring {primed} existing chat entries.")

        print()

        print("Send a NEW message from another IMVU user.")

        print("Press Ctrl+C to stop.")

        print("------------------------------------")



        while True:

            messages = controller.wait_for_new_chat_messages(

                timeout_ms=1000,

                poll_interval_ms=250,

            )



            for message in messages:

                print(

                    f"[IMVU CHAT] "

                    f"{message['username']}: "

                    f"{message['message']}"

                )

                print(

                    f"            entry={message['entry_id'] or '(none)'} "

                    f"user={message['user_id'] or '(none)'}"

                )



    except KeyboardInterrupt:

        print()

        print("------------------------------------")

        print("Live chat listener stopped.")

        print("------------------------------------")



    except Exception as error:

        print()

        print("ERROR:")

        print(error)



    finally:

        controller.disconnect()





if __name__ == "__main__":

    main()

