"""Browser smoke checks for PX WebShop.

Serve the project with `python3 -m http.server 8617 --bind 127.0.0.1 --protocol HTTP/1.1`.
In a test environment, install Playwright with `pip install playwright`,
run `python -m playwright install chromium firefox webkit`, and then run
`python tests/smoke.py`. Pass --axe /path/to/axe.min.js to check accessibility.
"""

import argparse
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import expect, sync_playwright


WIDTHS = (320, 360, 390, 428, 768, 820, 1024, 1280, 1440)
PLANS = (("Starter", "$250"), ("Business Premium", "$400"), ("Signature", "$750"))
PROJECTS = (
    ("tecnomarmol", "https://tecnomarmolpr.com"),
    ("university", "https://universityenvivo.com"),
    ("jp-boats", "https://jpresellerllc.com"),
)


def check_accessibility(page, axe_path, state):
    if not axe_path:
        return
    violations = page.evaluate(
        """async () => (await axe.run({
          runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']}
        })).violations.map(({id, nodes}) => ({id, targets: nodes.map(({target}) => target)}))"""
    )
    assert not violations, (state, violations)


def check_layout(page, base_url):
    page.set_viewport_size({"width": WIDTHS[0], "height": 844})
    assert page.goto(base_url).ok
    for width in WIDTHS:
        page.set_viewport_size({"width": width, "height": 900 if width >= 1024 else 844})
        layout = page.evaluate("""() => ({
          width: document.documentElement.scrollWidth,
          bodyWidth: document.body.scrollWidth,
          previewWidth: document.querySelector('.scene-wrap').offsetWidth,
          previewHeight: document.querySelector('.scene-wrap').offsetHeight,
          missing: [...document.querySelectorAll('a[href^="#"]')]
            .map(link => link.hash).filter(hash => !document.getElementById(hash.slice(1))),
          overlaps: [...document.querySelectorAll('main > section')]
            .slice(1).filter(section => section.previousElementSibling.getBoundingClientRect().bottom
              > section.getBoundingClientRect().top + 1).length
        })""")
        assert layout["width"] == layout["bodyWidth"] == width, (width, layout)
        assert 0 < layout["previewHeight"] < layout["previewWidth"], (width, layout)
        assert not layout["missing"] and not layout["overlaps"], (width, layout)
        menu_toggle = page.get_by_role("button", name="Menú")
        if width <= 860:
            expect(menu_toggle).to_be_visible()
            expect(page.locator("#primary-nav")).to_have_js_property("inert", True)
        else:
            expect(menu_toggle).to_be_hidden()
            expect(page.get_by_role("navigation", name="Navegación principal")).to_be_visible()


def check_menu(page, base_url):
    # WebKit on macOS uses Option+Tab to cycle through links by default.
    tab_key = "Alt+Tab" if page.context.browser.browser_type.name == "webkit" else "Tab"
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(base_url)
    page.keyboard.press(tab_key)
    expect(page.get_by_role("link", name="Ir al contenido")).to_be_focused()
    page.keyboard.press("Enter")
    expect(page.locator("main")).to_be_focused()

    page.goto(base_url)
    toggle = page.get_by_role("button", name="Menú")
    nav = page.get_by_role("navigation", name="Navegación principal")
    toggle.focus()
    page.keyboard.press("Enter")
    expect(toggle).to_have_attribute("aria-expanded", "true")
    page.keyboard.press(tab_key)
    expect(nav.get_by_role("link", name="Proyectos")).to_be_focused()
    page.keyboard.press("Escape")
    expect(toggle).to_be_focused()
    expect(toggle).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#primary-nav")).to_have_js_property("inert", True)

    for label, anchor in (
        ("Proyectos", "proyectos"),
        ("Servicios", "servicios"),
        ("Proceso", "proceso"),
        ("Planes", "pricing"),
        ("Cotizar mi web", "contacto"),
    ):
        toggle.press("Space")
        link = nav.get_by_role("link", name=label)
        link.press("Enter")
        expect(page).to_have_url(f"{base_url}#{anchor}")
        expect(page.locator(f"#{anchor}")).to_be_focused()
        expect(toggle).to_have_attribute("aria-expanded", "false")
        assert page.locator(f"#{anchor}").bounding_box()["y"] >= 65

    toggle.click()
    page.locator(".contact-copy > p.eyebrow").click()
    expect(toggle).to_have_attribute("aria-expanded", "false")

    toggle.click()
    page.set_viewport_size({"width": 1280, "height": 900})
    expect(nav).to_be_visible()
    expect(page.locator(".menu-toggle")).to_have_attribute("aria-expanded", "false")
    expect(page.locator("#primary-nav")).to_have_js_property("inert", False)
    page.set_viewport_size({"width": 390, "height": 844})
    expect(toggle).to_have_attribute("aria-expanded", "false")


def check_projects_and_plans(page, base_url):
    page.goto(base_url)
    page.get_by_role("link", name="Explorar proyectos").click()
    expect(page).to_have_url(f"{base_url}#proyectos")
    for project, url in PROJECTS:
        card = page.locator(f"#{project}")
        expect(card.get_by_role("link", name="Visitar proyecto", exact=False)).to_have_attribute("href", url)
        for picture in card.get_by_role("img").all():
            picture.scroll_into_view_if_needed()
            picture.evaluate("(image) => image.decode()")
            assert picture.evaluate("(image) => image.naturalWidth > 0")

    for index, (name, price) in enumerate(PLANS):
        plan = page.locator(".plan").nth(index)
        expect(plan.get_by_role("heading", name=name, exact=True)).to_be_visible()
        expect(plan.locator(".price")).to_contain_text(price)
        url = urlsplit(plan.get_by_role("link", name=f"Consultar {name}", exact=False).get_attribute("href"))
        assert (url.netloc, url.path) == ("wa.me", "/17876719928")
        assert f"plan {name}" in parse_qs(url.query)["text"][0]

    assert sorted(page.locator(".plan-example a").evaluate_all("(links) => links.map((link) => link.getAttribute('href'))")) == sorted(url for _, url in PROJECTS)
    for path in ("robots.txt", "sitemap.xml", "assets/px-social.jpg"):
        assert page.request.get(base_url + path).ok, path


def check_quote(page, base_url, axe_path):
    context = page.context
    handoffs = []
    requests = []

    def intercept_whatsapp(route):
        handoffs.append(route.request.url)
        route.fulfill(body="WhatsApp test endpoint", content_type="text/plain")

    def record_request(request):
        url = urlsplit(request.url)
        if not (request.method == "GET" and url.netloc == urlsplit(base_url).netloc
                and url.path.startswith(urlsplit(base_url).path + "assets/") and not url.query):
            requests.append(request.url)

    context.route("https://wa.me/**", intercept_whatsapp)
    page.goto(base_url)
    context.on("request", record_request)
    if axe_path:
        page.add_script_tag(path=axe_path)
    check_accessibility(page, axe_path, "initial document")
    page.get_by_role("link", name="Solicitar cotización", exact=True).click()

    prepare = page.get_by_role("button", name="Preparar mensaje")
    name = page.get_by_role("textbox", name="Nombre", exact=True)
    name.fill("   ")
    prepare.click()
    expect(name).to_be_focused()
    expect(name).to_have_attribute("aria-invalid", "true")
    expect(page.get_by_text("Escribe tu nombre.", exact=True)).to_be_visible()
    assert page.locator('[aria-invalid="true"]').count() == 4
    check_accessibility(page, axe_path, "form validation")

    name.fill("Persona de Prueba")
    page.get_by_label("Negocio o proyecto").fill("Estudio Ficticio & Co.")
    page.get_by_label("Servicio deseado").select_option("Business Premium")
    description = "Primera línea con acentos.\nSegunda línea con <texto> y 50%."
    page.get_by_label("Descripción del proyecto").fill(description)
    assert page.locator('[aria-invalid="true"]').count() == 0

    dialog = page.get_by_role("dialog", name="Revisa tu mensaje")
    prepare.click()
    expect(dialog).to_be_visible()
    expect(dialog.get_by_role("heading")).to_be_focused()
    expect(dialog.get_by_role("region", name="Borrador de cotización")).to_contain_text("Presupuesto estimado: Por definir")
    assert not handoffs and not requests, ("Preparing the preview must stay on the page.", requests)
    check_accessibility(page, axe_path, "quote preview")

    page.keyboard.press("Escape")
    expect(dialog).to_be_hidden()
    expect(prepare).to_be_focused()
    expect(name).to_have_value("Persona de Prueba")
    page.get_by_label("Presupuesto estimado", exact=False).select_option("$400–$749")

    prepare.click()
    dialog.get_by_role("button", name="Editar mensaje").click()
    expect(prepare).to_be_focused()
    prepare.click()

    draft = dialog.get_by_role("region", name="Borrador de cotización").text_content()
    assert "Presupuesto estimado: $400–$749" in draft
    assert "Negocio o proyecto: Estudio Ficticio & Co." in draft
    assert draft.endswith(description)
    mail = urlsplit(dialog.get_by_role("link", name="Abrir correo").get_attribute("href"))
    assert (mail.scheme, mail.path) == ("mailto", "pxcheco@pxwebshop.com")
    assert parse_qs(mail.query)["body"][0].replace("\r\n", "\n") == draft

    with page.expect_popup() as popup:
        dialog.get_by_role("link", name="Abrir WhatsApp", exact=False).click()
    popup.value.wait_for_load_state()
    opened = urlsplit(handoffs[0])
    assert (opened.netloc, opened.path) == ("wa.me", "/17876719928")
    assert parse_qs(opened.query)["text"][0] == draft
    popup.value.close()


def check_motion(page, base_url):
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(base_url)
    scene = page.locator(".scene-wrap")
    laptop = scene.locator(".macbook-a")
    transform = "(element) => getComputedStyle(element).transform"
    expect(laptop.locator(".code-panel")).to_be_visible()
    assert scene.locator(".macbook").count() == 2
    assert scene.locator(".glass-panel").count() == 0
    initial = laptop.evaluate(transform)
    page.wait_for_function("""() => {
      const movement = getComputedStyle(document.querySelector('.macbook-a')).translate;
      return parseFloat(movement.split(' ')[1]) < -3;
    }""")

    page.evaluate("scrollTo(0, 240)")
    page.wait_for_function("""() => parseFloat(
      document.querySelector('.scene-wrap').style.getPropertyValue('--scene-offset')
    ) > 0""")
    page.wait_for_function("pose => getComputedStyle(document.querySelector('.macbook-a')).transform !== pose", arg=initial)

    page.emulate_media(reduced_motion="reduce")
    page.wait_for_function("document.getAnimations().length === 0")
    assert laptop.evaluate(transform) == initial

    page.locator("#pricing").scroll_into_view_if_needed()
    assert page.locator(".plan").first.evaluate("(plan) => getComputedStyle(plan).opacity") == "1"

    page.set_viewport_size({"width": 390, "height": 844})
    page.emulate_media(reduced_motion="no-preference")
    page.goto(base_url)
    expect(laptop.locator(".code-panel")).to_be_visible()
    mobile_pose = laptop.evaluate(transform)
    page.evaluate("scrollTo(0, 160)")
    page.wait_for_function("pose => getComputedStyle(document.querySelector('.macbook-a')).transform !== pose", arg=mobile_pose)
    assert page.evaluate("document.documentElement.scrollWidth") == 390


def check_without_js(browser, base_url):
    page = browser.new_page(java_script_enabled=False, viewport={"width": 390, "height": 844})
    page.goto(base_url)
    expect(page.locator(".macbook-a .screen-ui")).to_be_visible()
    expect(page.get_by_role("link", name="Proyectos", exact=True).first).to_be_visible()
    expect(page.get_by_role("heading", name="Proyectos seleccionados")).to_be_visible()
    expect(page.get_by_role("button", name="Preparar mensaje")).to_be_hidden()
    expect(page.get_by_role("link", name="Correo electrónico", exact=False)).to_have_attribute("href", "mailto:pxcheco@pxwebshop.com?subject=Cotizaci%C3%B3n%20de%20dise%C3%B1o%20web")
    page.close()


def run(browser, base_url, axe_path):
    page = browser.new_page(locale="es-PR", reduced_motion="reduce")
    problems = []
    page.on("pageerror", lambda error: problems.append(str(error)))
    page.on("console", lambda message: problems.append(message.text) if message.type == "error" else None)
    page.on("response", lambda response: problems.append(f"{response.status} {response.url}") if response.status >= 400 else None)
    def record_failure(request):
        # Browsers cancel obsolete image requests when the viewport changes.
        failure = request.failure or "unknown request failure"
        if failure.casefold() not in {"net::err_aborted", "ns_binding_aborted", "cancelled"}:
            problems.append(f"{failure} {request.url}")

    page.on("requestfailed", record_failure)
    check_layout(page, base_url)
    check_menu(page, base_url)
    check_projects_and_plans(page, base_url)
    check_quote(page, base_url, axe_path)
    page.emulate_media(reduced_motion="no-preference")
    check_motion(page, base_url)
    check_without_js(browser, base_url)
    assert not problems, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8617/")
    parser.add_argument("--axe", type=Path)
    parser.add_argument("--chrome-channel", help="Set to 'chrome' to use installed Google Chrome.")
    parser.add_argument("--browser", action="append", choices=("chromium", "firefox", "webkit"))
    args = parser.parse_args()
    with sync_playwright() as playwright:
        for name in args.browser or ("chromium", "firefox", "webkit"):
            options = {"channel": args.chrome_channel} if name == "chromium" and args.chrome_channel else {}
            browser = getattr(playwright, name).launch(**options)
            try:
                run(browser, args.url.rstrip("/") + "/", args.axe)
                print(f"{name} {browser.version}: {len(WIDTHS)} widths, keyboard, links, quote, motion, no JS"
                      + (", axe WCAG 2.1 AA" if args.axe else "") + " passed")
            finally:
                browser.close()


if __name__ == "__main__":
    main()
