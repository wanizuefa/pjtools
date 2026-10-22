/* CineScope — shared page behaviour (loaded on every page). */

const prefersReducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* Read a message to screen-reader users through the shared live region. */
function announce(message) {
  const region = document.getElementById("live-region");
  if (!region) return;
  region.textContent = "";
  // A short delay makes screen readers notice the change reliably.
  window.setTimeout(() => { region.textContent = message; }, 120);
}

/* ---------------------------------------------------------------------------
   Navbar (mobile menu)
   ------------------------------------------------------------------------- */
function initNavToggle() {
  const toggle = document.querySelector(".nav-toggle");
  const menu = document.getElementById("nav-menu");
  if (!toggle || !menu) return;

  const setOpen = (open) => {
    toggle.setAttribute("aria-expanded", String(open));
    menu.classList.toggle("is-open", open);
  };

  toggle.addEventListener("click", () => {
    setOpen(toggle.getAttribute("aria-expanded") !== "true");
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && menu.classList.contains("is-open")) {
      setOpen(false);
      toggle.focus();
    }
  });
}

/* ---------------------------------------------------------------------------
   Marquee signs: place light bulbs evenly around the border
   ------------------------------------------------------------------------- */
function buildMarqueeBulbs(sign) {
  // Rebuild only when the size really changed (ResizeObserver also fires once
  // on start, which would otherwise restart the light-up sequence).
  const size = `${sign.clientWidth}x${sign.clientHeight}`;
  if (sign.dataset.bulbSize === size) return;
  sign.dataset.bulbSize = size;

  let ring = sign.querySelector(".marquee__bulbs");
  if (!ring) {
    ring = document.createElement("div");
    ring.className = "marquee__bulbs";
    ring.setAttribute("aria-hidden", "true");
    sign.prepend(ring);
  }
  ring.textContent = "";

  const width = sign.clientWidth;
  const height = sign.clientHeight;
  const inset = 10;    // distance from the edge
  const spacing = 24;  // approximate distance between bulbs
  const innerW = width - inset * 2;
  const innerH = height - inset * 2;
  const countX = Math.max(2, Math.round(innerW / spacing));
  const countY = Math.max(1, Math.round(innerH / spacing));

  // Walk clockwise around the rectangle so the chase animation runs in a loop.
  const points = [];
  for (let i = 0; i < countX; i++) points.push([inset + (innerW * i) / countX, inset]);
  for (let i = 0; i < countY; i++) points.push([width - inset, inset + (innerH * i) / countY]);
  for (let i = countX; i > 0; i--) points.push([inset + (innerW * i) / countX, height - inset]);
  for (let i = countY; i > 0; i--) points.push([inset, inset + (innerH * i) / countY]);

  const fragment = document.createDocumentFragment();
  points.forEach(([x, y], index) => {
    const bulb = document.createElement("span");
    bulb.className = `bulb bulb--${index % 3}`;
    bulb.style.left = `${x}px`;
    bulb.style.top = `${y}px`;
    fragment.appendChild(bulb);
  });
  ring.appendChild(fragment);
}

/* Signs with data-light-sequence switch their bulbs on one by one at page
   load, hold steady, then all start the chase together (so it stays in sync). */
function lightBulbsInSequence(sign) {
  const bulbs = Array.from(sign.querySelectorAll(".bulb"));
  if (prefersReducedMotion() || !bulbs.length) return;
  const step = Math.min(30, 1800 / bulbs.length);
  sign.classList.add("is-lighting");
  bulbs.forEach((bulb, index) => {
    window.setTimeout(() => bulb.classList.add("is-on"), index * step);
  });
  window.setTimeout(() => sign.classList.remove("is-lighting"), bulbs.length * step + 500);
}

function initMarquees() {
  const signs = document.querySelectorAll("[data-marquee]");
  signs.forEach((sign) => buildMarqueeBulbs(sign));
  document.querySelectorAll("[data-light-sequence]").forEach(lightBulbsInSequence);

  if ("ResizeObserver" in window) {
    const observer = new ResizeObserver((entries) => {
      entries.forEach((entry) => buildMarqueeBulbs(entry.target));
    });
    signs.forEach((sign) => observer.observe(sign));
  }
}

/* ---------------------------------------------------------------------------
   Sound toggle (🔊 / 🔇) and button click sounds
   ------------------------------------------------------------------------- */
function initSound() {
  const toggle = document.getElementById("sound-toggle");
  if (!toggle || typeof CineAudio === "undefined") return;

  const render = () => {
    const on = CineAudio.isEnabled();
    toggle.setAttribute("aria-pressed", String(on));
    toggle.querySelector(".sound-toggle__icon").textContent = on ? "🔊" : "🔇";
    toggle.title = on ? "ปิดเสียงประกอบ" : "เปิดเสียงประกอบ";
  };

  toggle.addEventListener("click", () => {
    CineAudio.setEnabled(!CineAudio.isEnabled());
    render();
    CineAudio.play("click");
    announce(CineAudio.isEnabled() ? "เปิดเสียงประกอบแล้ว" : "ปิดเสียงประกอบแล้ว");
  });
  render();

  // Every button / button-like link makes a soft click (when sound is on).
  document.addEventListener("click", (event) => {
    const target = event.target.closest("button, .btn");
    if (target && !target.hasAttribute("data-no-click-sound")) CineAudio.play("click");
  });
}

/* ---------------------------------------------------------------------------
   Flash messages (movie tickets)
   ------------------------------------------------------------------------- */
function initFlashMessages() {
  const tickets = document.querySelectorAll("[data-flash]");
  if (!tickets.length) return;

  const messages = [];
  tickets.forEach((ticket) => {
    const title = ticket.querySelector(".ticket__title").textContent.trim();
    const message = ticket.querySelector(".ticket__message").textContent.trim();
    messages.push(`${title} ${message}`);

    ticket.querySelector(".ticket__close").addEventListener("click", () => ticket.remove());
  });
  announce(messages.join(" "));

  if (document.querySelector('[data-flash][data-sound="clapper"]') && typeof CineAudio !== "undefined") {
    CineAudio.play("clapper");
  }
}

/* ---------------------------------------------------------------------------
   Delete confirmation: any <form data-confirm="..."> asks first
   ------------------------------------------------------------------------- */
function initConfirmDialogs() {
  const dialog = document.getElementById("confirm-dialog");
  let pendingForm = null;
  let returnFocusTo = null;

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!form.matches("form[data-confirm]")) return;
    event.preventDefault();

    const message = form.getAttribute("data-confirm");
    if (!dialog || typeof dialog.showModal !== "function") {
      if (window.confirm(message)) {
        markUserAction();
        showLoading(form.dataset.loadingText);
        form.submit();
      }
      return;
    }
    pendingForm = form;
    returnFocusTo = event.submitter || document.activeElement;
    document.getElementById("confirm-message").textContent = message;
    dialog.returnValue = "";
    dialog.showModal();
  });

  if (!dialog) return;
  dialog.addEventListener("close", () => {
    if (dialog.returnValue === "confirm" && pendingForm) {
      markUserAction();
      showLoading(pendingForm.dataset.loadingText);
      pendingForm.submit(); // submit() skips the submit event, so no loop
    } else if (returnFocusTo) {
      returnFocusTo.focus();
    }
    pendingForm = null;
  });
}

/* ---------------------------------------------------------------------------
   Client-side validation for <form data-validate>
   The same rules are checked again on the server (data_service.validate_movie).
   ------------------------------------------------------------------------- */
const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];

function isValidReleaseDate(text) {
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  if (iso) {
    const [year, month, day] = [Number(iso[1]), Number(iso[2]), Number(iso[3])];
    const date = new Date(Date.UTC(year, month - 1, day));
    return date.getUTCFullYear() === year && date.getUTCMonth() === month - 1 && date.getUTCDate() === day;
  }
  const partial = /^([A-Za-z]+) (\d{4})$/.exec(text);
  if (partial) return MONTHS.includes(partial[1]);
  return /^\d{4}$/.test(text);
}

function rangeMessage(label, min, max) {
  if (max === null) return min === 0 ? `${label}ต้องไม่ติดลบ` : `${label}ต้องไม่น้อยกว่า ${min}`;
  return `${label}ต้องอยู่ระหว่าง ${min} ถึง ${max}`;
}

function validateField(input) {
  const label = input.dataset.label || input.name;
  const value = input.value.trim();
  const isSelect = input.tagName === "SELECT";

  // A number input containing text reports value "" plus validity.badInput.
  if (input.validity && input.validity.badInput) return `${label}ต้องเป็นตัวเลข`;

  if (value === "") {
    if (input.hasAttribute("data-required")) {
      return isSelect ? `กรุณาเลือก${label}` : `กรุณากรอก${label}`;
    }
    return "";
  }

  if (input.hasAttribute("data-release-date") && !isValidReleaseDate(value)) {
    return "รูปแบบวันฉายไม่ถูกต้อง ใช้ ปี-เดือน-วัน เช่น 1980-06-13 (หรือ November 1980 / 1980 ถ้าไม่ทราบวันที่)";
  }

  const hasMin = input.dataset.min !== undefined;
  const hasMax = input.dataset.max !== undefined;
  if (input.type === "number" || hasMin || hasMax) {
    const number = Number(value.replace(/,/g, ""));
    if (!Number.isFinite(number)) return `${label}ต้องเป็นตัวเลข`;
    if (input.hasAttribute("data-integer") && !Number.isInteger(number)) return `${label}ต้องเป็นจำนวนเต็ม`;
    const min = hasMin ? Number(input.dataset.min) : null;
    const max = hasMax ? Number(input.dataset.max) : null;
    if ((min !== null && number < min) || (max !== null && number > max)) {
      return rangeMessage(label, min, max);
    }
  }
  return "";
}

function showFieldError(input, message) {
  const field = input.closest(".field");
  const error = document.getElementById(`err-${input.name}`);
  if (!field || !error) return;
  field.classList.toggle("has-error", Boolean(message));
  error.querySelector(".field-error__text").textContent = message;
  error.hidden = !message;
  if (message) input.setAttribute("aria-invalid", "true");
  else input.removeAttribute("aria-invalid");
}

function updateErrorSummary(errors) {
  const summary = document.getElementById("error-summary");
  if (!summary) return;
  const list = document.getElementById("error-list");
  list.textContent = "";
  errors.forEach(({ input, message }) => {
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = `#${input.id}`;
    link.textContent = message;
    link.addEventListener("click", (event) => {
      event.preventDefault();
      input.focus();
    });
    item.appendChild(link);
    list.appendChild(item);
  });
  document.getElementById("error-count").textContent = errors.length;
  summary.hidden = errors.length === 0;
}

function initFormValidation() {
  document.querySelectorAll("form[data-validate]").forEach((form) => {
    const inputs = Array.from(form.querySelectorAll("input[data-label], select[data-label]"));
    let submitting = false;

    inputs.forEach((input) => {
      // Validate when leaving a field, and re-check while fixing an error.
      input.addEventListener("blur", () => showFieldError(input, validateField(input)));
      input.addEventListener("input", () => {
        if (input.getAttribute("aria-invalid") === "true") showFieldError(input, validateField(input));
      });
      input.addEventListener("change", () => {
        if (input.tagName === "SELECT") showFieldError(input, validateField(input));
      });
    });

    form.addEventListener("submit", (event) => {
      if (submitting) {
        event.preventDefault();
        return;
      }
      const errors = [];
      inputs.forEach((input) => {
        const message = validateField(input);
        showFieldError(input, message);
        if (message) errors.push({ input, message });
      });
      updateErrorSummary(errors);

      if (errors.length) {
        event.preventDefault();
        errors[0].input.focus();
        announce(`ยังบันทึกไม่ได้ กรุณาแก้ไขข้อมูล ${errors.length} ช่อง`);
        return;
      }

      // Valid: close the clapperboard, then send the form.
      submitting = true;
      markUserAction();
      const button = form.querySelector('[type="submit"]');
      if (button) button.disabled = true;
      // Let the clapperboard snap shut first, then show the loading screen.
      const clapper = document.getElementById("clapper");
      if (clapper && !prefersReducedMotion()) {
        event.preventDefault();
        clapper.classList.add("is-clapping");
        window.setTimeout(() => {
          showLoading(form.dataset.loadingText);
          form.submit();
        }, 380);
      } else {
        showLoading(form.dataset.loadingText);
      }
    });
  });

  // Server-side errors: move focus to the summary so it is read out first.
  const summary = document.getElementById("error-summary");
  if (summary && !summary.hidden) summary.focus();
}

/* ---------------------------------------------------------------------------
   Counters that run up like a cash counter: <span data-count-to="7669"
   data-format="number|money|decimal|year">. The server already printed the
   final value, so without JavaScript (or with reduced motion) it simply stays.
   ------------------------------------------------------------------------- */
function formatCounter(value, format) {
  if (format === "money") {
    const amount = Math.abs(value);
    if (amount >= 1e9) return `$${(value / 1e9).toFixed(1)}B`;
    if (amount >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
    if (amount >= 1e3) return `$${(value / 1e3).toFixed(0)}K`;
    return `$${value.toFixed(0)}`;
  }
  if (format === "decimal") return value.toFixed(2);
  if (format === "year") return String(Math.round(value));
  return Math.round(value).toLocaleString("en-US");
}

function initCounters() {
  const counters = document.querySelectorAll("[data-count-to]");
  if (!counters.length || prefersReducedMotion()) return;

  const duration = 1800;
  const start = performance.now();
  const easeOut = (t) => 1 - Math.pow(1 - t, 3);
  const items = Array.from(counters).map((el) => ({
    el,
    from: Number(el.dataset.countFrom || 0),
    to: Number(el.dataset.countTo),
    format: el.dataset.format,
    final: el.textContent,
  }));
  // Screen readers get the final value straight away.
  items.forEach((item) => item.el.setAttribute("aria-label", item.final.trim()));

  const tick = (now) => {
    const t = Math.min(1, (now - start) / duration);
    items.forEach((item) => {
      item.el.textContent = t < 1
        ? formatCounter(item.from + (item.to - item.from) * easeOut(t), item.format)
        : item.final;
    });
    if (t < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/* Remember that the user pressed save/delete, so the next page may play its
   confirmation sound (see CineAudio.markUserAction). */
function markUserAction() {
  if (typeof CineAudio !== "undefined") CineAudio.markUserAction();
}

/* ---------------------------------------------------------------------------
   Loading screen while a save/delete is written to Excel (takes ~2 seconds).
   A film-leader countdown 3-2-1 runs until the next page loads.
   ------------------------------------------------------------------------- */
const loading = { timer: null, slowTimer: null };

function showLoading(title) {
  const screen = document.getElementById("loading-screen");
  if (!screen) return;
  document.getElementById("loading-title").textContent = title || "กำลังบันทึกลง Excel";
  document.getElementById("loading-text").textContent = "กำลังเขียนไฟล์ data/movies.xlsx กรุณารอสักครู่";
  screen.hidden = false;
  document.body.setAttribute("aria-busy", "true");

  const number = document.getElementById("leader-number");
  let count = 3;
  number.textContent = String(count);
  window.clearInterval(loading.timer);
  if (!prefersReducedMotion()) {
    loading.timer = window.setInterval(() => {
      count = count === 1 ? 3 : count - 1;
      number.textContent = String(count);
    }, 1000);
  }
  // If the server takes unusually long, say so instead of spinning silently.
  window.clearTimeout(loading.slowTimer);
  loading.slowTimer = window.setTimeout(() => {
    document.getElementById("loading-text").textContent =
      "ใช้เวลานานกว่าปกติ ถ้าหน้านี้ไม่เปลี่ยน ให้ตรวจว่าเว็บยังรันอยู่ และไม่ได้เปิดไฟล์ movies.xlsx ค้างไว้";
  }, 15000);
}

function hideLoading() {
  const screen = document.getElementById("loading-screen");
  if (!screen) return;
  screen.hidden = true;
  document.body.removeAttribute("aria-busy");
  window.clearInterval(loading.timer);
  window.clearTimeout(loading.slowTimer);
}

// Coming back with the browser's Back button can restore this page from cache
// with the loading screen still showing; hide it again.
window.addEventListener("pageshow", hideLoading);

document.addEventListener("DOMContentLoaded", () => {
  initNavToggle();
  initMarquees();
  initCounters();
  initSound();
  initFlashMessages();
  initConfirmDialogs();
  initFormValidation();
});
