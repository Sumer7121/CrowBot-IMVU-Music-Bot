from bot.imvu_web_controller import IMVUWebController


def clean_text(value):
    if value is None:
        return ""

    return " ".join(
        str(value).split()
    )


def print_element_info(
    element,
    label
):
    try:
        info = element.evaluate(
            """
            (el) => ({
                tag: el.tagName,
                id: el.id || "",
                className:
                    typeof el.className === "string"
                    ? el.className
                    : "",
                placeholder:
                    el.getAttribute("placeholder") || "",
                ariaLabel:
                    el.getAttribute("aria-label") || "",
                title:
                    el.getAttribute("title") || "",
                role:
                    el.getAttribute("role") || "",
                type:
                    el.getAttribute("type") || "",
                contenteditable:
                    el.getAttribute("contenteditable") || "",
                text:
                    el.innerText || el.textContent || "",
                outerHTML:
                    el.outerHTML || ""
            })
            """
        )

        print()
        print("=" * 70)
        print(label)
        print("=" * 70)

        print(
            "TAG:",
            info.get("tag", "")
        )

        print(
            "ID:",
            info.get("id", "")
        )

        print(
            "CLASS:",
            info.get("className", "")
        )

        print(
            "PLACEHOLDER:",
            info.get("placeholder", "")
        )

        print(
            "ARIA-LABEL:",
            info.get("ariaLabel", "")
        )

        print(
            "TITLE:",
            info.get("title", "")
        )

        print(
            "ROLE:",
            info.get("role", "")
        )

        print(
            "TYPE:",
            info.get("type", "")
        )

        print(
            "CONTENTEDITABLE:",
            info.get("contenteditable", "")
        )

        print(
            "TEXT:",
            clean_text(
                info.get("text", "")
            )
        )

        print()
        print("OUTER HTML:")
        print(
            info.get("outerHTML", "")
        )

    except Exception as error:

        print(
            f"{label} ERROR: {error}"
        )


def inspect_locator(
    locator,
    label,
    max_results=10
):
    try:
        count = locator.count()

    except Exception as error:

        print(
            f"{label}: ERROR: {error}"
        )

        return

    print()
    print(
        f"{label}: {count} match(es)"
    )

    for index in range(
        min(
            count,
            max_results
        )
    ):

        try:
            element = locator.nth(index)

            if not element.is_visible():
                continue

            print_element_info(
                element,
                f"{label} #{index}"
            )

        except Exception as error:

            print(
                f"{label} #{index} ERROR: "
                f"{error}"
            )


def main():

    print()
    print("IMVU CHAT COMPOSER INSPECTION")
    print("-" * 70)

    controller = (
        IMVUWebController()
    )

    try:

        controller.connect()

        page = (
            controller.find_imvu_room()
        )

        if not page:

            print(
                "ERROR: No IMVU room "
                "tab was found."
            )

            return

        print()
        print(
            "ROOM:",
            controller.get_room_url()
        )

        print()
        print(
            "This test is READ ONLY."
        )

        print(
            "It will NOT type or send "
            "anything into IMVU."
        )

        # =====================================================
        # EXACT PLACEHOLDER
        # =====================================================

        inspect_locator(
            page.get_by_placeholder(
                "Say something…"
            ),
            "EXACT PLACEHOLDER: Say something…"
        )

        # Some browsers/pages may expose three periods instead
        # of the Unicode ellipsis character.
        inspect_locator(
            page.get_by_placeholder(
                "Say something..."
            ),
            "PLACEHOLDER: Say something..."
        )

        # =====================================================
        # TEXTAREA
        # =====================================================

        inspect_locator(
            page.locator(
                "textarea"
            ),
            "VISIBLE TEXTAREA"
        )

        # =====================================================
        # TEXT INPUTS
        # =====================================================

        inspect_locator(
            page.locator(
                'input[type="text"]'
            ),
            "VISIBLE TEXT INPUT"
        )

        # =====================================================
        # CONTENTEDITABLE
        # =====================================================

        inspect_locator(
            page.locator(
                '[contenteditable="true"]'
            ),
            "VISIBLE CONTENTEDITABLE"
        )

        # =====================================================
        # SEND BUTTON
        # =====================================================

        inspect_locator(
            page.get_by_role(
                "button",
                name="SEND",
                exact=True
            ),
            "EXACT SEND BUTTON"
        )

        # =====================================================
        # BUTTONS CONTAINING SEND
        # =====================================================

        inspect_locator(
            page.locator(
                "button"
            ).filter(
                has_text="SEND"
            ),
            "BUTTON CONTAINING SEND"
        )

        # =====================================================
        # CHAT PANE
        # =====================================================

        inspect_locator(
            page.locator(
                ".chat-pane"
            ),
            "CHAT PANE",
            max_results=3
        )

        print()
        print("-" * 70)
        print(
            "INSPECTION COMPLETE"
        )
        print("-" * 70)

    except Exception as error:

        print()
        print(
            "ERROR:",
            error
        )

    finally:

        controller.disconnect()


if __name__ == "__main__":
    main()