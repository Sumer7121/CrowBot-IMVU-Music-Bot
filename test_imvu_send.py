from bot.imvu_web_controller import IMVUWebController


TEST_MESSAGE = "IMVU Music Bot send test"


def main():
    controller = IMVUWebController()

    try:
        print("Connecting to bot Chrome...")
        controller.connect()

        page = controller.find_imvu_room()

        if not page:
            raise RuntimeError(
                "No IMVU room tab was found."
            )

        print(
            "Room:",
            controller.get_room_url()
        )

        # Exact composer discovered from the live IMVU DOM.
        chat_input = page.locator(
            'textarea[placeholder="Say something..."]'
        )

        if chat_input.count() != 1:
            raise RuntimeError(
                "Expected exactly one IMVU chat textarea, "
                f"but found {chat_input.count()}."
            )

        if not chat_input.is_visible():
            raise RuntimeError(
                "IMVU chat textarea exists but is not visible."
            )

        # Exact SEND button discovered from the live IMVU DOM.
        send_button = page.locator(
            "button.btn-send"
        )

        if send_button.count() != 1:
            raise RuntimeError(
                "Expected exactly one IMVU SEND button, "
                f"but found {send_button.count()}."
            )

        print(
            "Typing:",
            TEST_MESSAGE
        )

        chat_input.fill(
            TEST_MESSAGE
        )

        # Filling the textarea should enable SEND.
        send_button.wait_for(
            state="visible",
            timeout=5000
        )

        page.wait_for_timeout(300)

        if send_button.is_disabled():
            raise RuntimeError(
                "SEND button is still disabled after "
                "entering the test message."
            )

        print("Clicking SEND...")

        send_button.click(
            timeout=5000
        )

        page.wait_for_timeout(1000)

        print()
        print("SUCCESS: SEND button clicked.")
        print(
            "Check the IMVU room for:"
        )
        print(TEST_MESSAGE)

    except Exception as error:
        print()
        print(
            "SEND TEST FAILED:",
            error
        )

    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()
