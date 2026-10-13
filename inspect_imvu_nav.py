from bot.imvu_web_controller import IMVUWebController

c = IMVUWebController()

try:
    c.connect()
    page = c.find_imvu_room()

    if not page:
        print("ERROR: IMVU room not found.")
        raise SystemExit

    print("\nNAV ELEMENTS")
    print("=" * 70)

    items = page.locator("[data-nav]")

    for i in range(items.count()):
        el = items.nth(i)

        try:
            print({
                "index": i,
                "tag": el.evaluate("(e) => e.tagName"),
                "data-nav": el.get_attribute("data-nav"),
                "class": el.get_attribute("class"),
                "text": el.inner_text().strip(),
                "visible": el.is_visible(),
            })
        except Exception as e:
            print("ERROR:", e)

finally:
    c.disconnect()
