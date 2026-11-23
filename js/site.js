"use strict";

const mobileLayout = window.matchMedia("(max-width: 860px)");
const topbar = document.querySelector(".topbar");
const menuButton = document.querySelector(".menu-toggle");
const navigation = document.querySelector("#primary-nav");

function setMenuOpen(open) {
  menuButton.setAttribute("aria-expanded", String(open));
  navigation.inert = mobileLayout.matches && !open;
}

menuButton.addEventListener("click", () => {
  setMenuOpen(menuButton.getAttribute("aria-expanded") === "false");
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || menuButton.getAttribute("aria-expanded") !== "true") return;
  event.preventDefault();
  menuButton.focus();
  setMenuOpen(false);
});

document.addEventListener("click", (event) => {
  if (!topbar.contains(event.target)) setMenuOpen(false);
});

topbar.addEventListener("focusout", (event) => {
  if (event.relatedTarget && !topbar.contains(event.relatedTarget)) setMenuOpen(false);
});

topbar.addEventListener("click", (event) => {
  const link = event.target.closest('a[href^="#"]');
  if (!link || !mobileLayout.matches || menuButton.getAttribute("aria-expanded") !== "true") return;
  if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;

  const destination = document.querySelector(link.hash);
  if (destination) {
    destination.tabIndex = -1;
    destination.focus({ preventScroll: true });
  }
  setMenuOpen(false);
});

mobileLayout.addEventListener("change", () => {
  if (mobileLayout.matches && navigation.contains(document.activeElement)) menuButton.focus();
  setMenuOpen(false);
});

setMenuOpen(false);
menuButton.hidden = false;
topbar.dataset.menuReady = "";

const quoteForm = document.querySelector("#quote-form");
const quoteDialog = document.querySelector("#quote-preview");
const preview = document.querySelector("#preview-message");
const whatsapp = document.querySelector("#quote-whatsapp");
const email = document.querySelector("#quote-email");
const prepareButton = document.querySelector("#prepare-quote");
const whatsappContact = whatsapp.href;
const emailContact = email.href;

if (typeof quoteDialog.showModal === "function") {
  const requiredFields = [...quoteForm.querySelectorAll("[required]")];

  function validateField(field) {
    const valid = field.value.trim() !== "";
    const error = document.getElementById(field.getAttribute("aria-describedby"));
    error.hidden = valid;
    if (valid) field.removeAttribute("aria-invalid");
    else field.setAttribute("aria-invalid", "true");
    return valid;
  }

  for (const field of requiredFields) {
    field.addEventListener("input", () => {
      if (field.hasAttribute("aria-invalid")) validateField(field);
    });
  }

  quoteForm.addEventListener("submit", (event) => {
    event.preventDefault();

    const invalidFields = requiredFields.filter((field) => !validateField(field));
    if (invalidFields.length) {
      invalidFields[0].focus();
      return;
    }

    const details = new FormData(quoteForm);
    const name = details.get("name").trim();
    const business = details.get("business").trim();
    const description = details.get("description").trim();
    const message = [
      "Hola, PX WebShop. Quisiera solicitar una cotización.",
      "",
      `Nombre: ${name}`,
      `Negocio o proyecto: ${business}`,
      `Servicio: ${details.get("service")}`,
      `Presupuesto estimado: ${details.get("budget") || "Por definir"}`,
      "",
      "Descripción del proyecto:",
      description
    ].join("\n");

    const whatsappUrl = new URL(whatsappContact);
    whatsappUrl.searchParams.set("text", message);
    const emailQuery = new URLSearchParams({
      subject: "Cotización de diseño web",
      body: message.replaceAll("\n", "\r\n")
    }).toString().replaceAll("+", "%20");

    preview.textContent = message;
    whatsapp.href = whatsappUrl.href;
    email.href = `${emailContact}?${emailQuery}`;
    quoteDialog.showModal();
    preview.scrollTop = 0;
  });

  quoteDialog.addEventListener("close", () => {
    preview.textContent = "";
    whatsapp.href = whatsappContact;
    email.href = emailContact;
    prepareButton.focus();
  });

  quoteForm.noValidate = true;
  quoteForm.hidden = false;
}

document.querySelector("[data-current-year]").textContent = new Date().getFullYear();

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
const heroScene = document.querySelector(".scene-wrap");
const heroMotion = window.matchMedia("(prefers-reduced-motion: no-preference)");
let heroFrame = 0;
let heroOffset = 0;
let heroPointer = null;
let heroPointerChanged = false;

function queueHeroMotion() {
  if (!heroMotion.matches || heroFrame) return;

  const offset = Math.max(0, Math.min(24, Math.round(window.scrollY * .08)));
  if (!heroPointerChanged && offset === heroOffset) return;

  heroFrame = requestAnimationFrame(() => {
    heroFrame = 0;
    if (offset !== heroOffset) {
      heroOffset = offset;
      heroScene.style.setProperty("--scene-offset", `${heroOffset}px`);
      heroScene.style.setProperty("--scene-turn", `${heroOffset * .3}deg`);
    }
    if (!heroPointerChanged) return;

    heroPointerChanged = false;
    let x = 0;
    let y = 0;
    if (heroPointer) {
      const bounds = heroScene.getBoundingClientRect();
      x = (heroPointer.clientX - bounds.left) / bounds.width - .5;
      y = (heroPointer.clientY - bounds.top) / bounds.height - .5;
    }
    heroScene.style.setProperty("--scene-x", x.toFixed(3));
    heroScene.style.setProperty("--scene-y", y.toFixed(3));
  });
}

function updateHeroMotion() {
  if (heroMotion.matches) {
    window.addEventListener("scroll", queueHeroMotion, { passive: true });
    queueHeroMotion();
  } else {
    window.removeEventListener("scroll", queueHeroMotion);
    cancelAnimationFrame(heroFrame);
    heroFrame = 0;
    heroOffset = 0;
    heroPointer = null;
    heroPointerChanged = false;
    for (const property of ["--scene-offset", "--scene-turn", "--scene-x", "--scene-y"]) {
      heroScene.style.removeProperty(property);
    }
  }
}

heroScene.addEventListener("pointermove", (event) => {
  if (!heroMotion.matches || event.pointerType !== "mouse") return;
  heroPointer = event;
  heroPointerChanged = true;
  queueHeroMotion();
}, { passive: true });

heroScene.addEventListener("pointerleave", () => {
  if (!heroPointer) return;
  heroPointer = null;
  heroPointerChanged = true;
  queueHeroMotion();
});

heroMotion.addEventListener("change", updateHeroMotion);
updateHeroMotion();

// Animate only when entering the viewport. The underlying content stays visible.
if ("IntersectionObserver" in window && typeof Element.prototype.animate === "function") {
  const revealTargets = [...document.querySelectorAll(".reveal")];
  const animations = new Map();

  const observer = new IntersectionObserver((entries) => {
    if (reducedMotion.matches) return;
    const visibleEntries = entries.filter((entry) => entry.isIntersecting);

    visibleEntries.sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
    visibleEntries.forEach(({ target }, index) => {
      observer.unobserve(target);
      if (target.matches(":focus-within")) return;
      const animation = target.animate(
        [{ opacity: .62, transform: "translateY(12px)" }, { opacity: 1, transform: "none" }],
        { duration: 440, delay: Math.min(index, 3) * 55, easing: "cubic-bezier(.22,.61,.36,1)", fill: "backwards" }
      );
      animations.set(target, animation);
      animation.onfinish = animation.oncancel = () => animations.delete(target);
    });
  }, { threshold: .12 });

  function updateReveals() {
    observer.disconnect();
    for (const animation of animations.values()) animation.cancel();
    if (reducedMotion.matches) return;
    for (const target of revealTargets) {
      if (target.getBoundingClientRect().top >= window.innerHeight) observer.observe(target);
    }
  }

  document.addEventListener("focusin", (event) => {
    animations.get(event.target.closest(".reveal"))?.cancel();
  });
  reducedMotion.addEventListener("change", updateReveals);
  updateReveals();
}
