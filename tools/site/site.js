// Скрипт сайта FODB. Исходник лежит в tools/site, gen_site.py копирует его в GiDo.

// Плавно показывает блоки, когда они попадают на экран.
const blocks = document.querySelectorAll(".reveal");
if ("IntersectionObserver" in window) {
  const watcher = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add("in");
        watcher.unobserve(entry.target); // показали один раз, дальше следить незачем
      }
    }
  }, { rootMargin: "0px 0px -8% 0px" });
  blocks.forEach((block) => watcher.observe(block));
} else {
  // Старый браузер: просто показываем всё сразу.
  blocks.forEach((block) => block.classList.add("in"));
}

// Кнопка темы: переключает светлую и тёмную и запоминает выбор этого человека.
const themeButton = document.querySelector(".theme");
themeButton.addEventListener("click", () => {
  const saved = document.documentElement.dataset.theme;
  const light = saved ? saved === "light" : matchMedia("(prefers-color-scheme: light)").matches;
  const next = light ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("fodb-theme", next); } catch (error) { /* хранилище запрещено: выбор действует до перехода */ }
});

// Выбор языка в шапке запоминается: главная страница больше не будет определять его сама.
document.querySelectorAll(".langs a[data-code]").forEach((link) => {
  link.addEventListener("click", () => {
    try { localStorage.setItem("fodb-language", link.dataset.code); } catch (error) { /* ничего страшного */ }
  });
});

// Закрывает список языков при щелчке мимо него.
document.addEventListener("click", (event) => {
  const menu = document.querySelector(".langs[open]");
  if (menu && !menu.contains(event.target)) {
    menu.removeAttribute("open");
  }
});

// ---------- Фон с параллаксом ----------
// Слои фона создаются здесь, чтобы не повторять их в каждой странице.
const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
const scene = document.createElement("div");
scene.className = "scene";
scene.setAttribute("aria-hidden", "true");
// depth: насколько слой отзывается на прокрутку и мышь. Чем больше, тем он как будто ближе.
const layers = [];
function addLayer(className, depth, style) {
  const element = document.createElement("div");
  element.className = className;
  if (style) Object.assign(element.style, style);
  scene.appendChild(element);
  layers.push({ element, depth });
  return element;
}
addLayer("dots", 0.08);
addLayer("glow a", 0.16);
addLayer("glow b", 0.26);
// Летающие ячейки стоят на одних и тех же местах при каждой загрузке: формула вместо случайных чисел.
for (let i = 0; i < 22; i += 1) {
  const size = 12 + (i * 7) % 34;
  addLayer("pad", 0.12 + ((i * 13) % 10) / 16, {
    width: size + "px",
    height: size + "px",
    left: (i * 37) % 100 + "%",
    top: (i * 61) % 140 + "%",
    opacity: 0.35 + ((i * 5) % 7) / 10,
  });
}
document.body.prepend(scene);

// Двигаем слои не чаще одного раза за кадр: так анимация не грузит браузер.
let mouseX = 0;
let mouseY = 0;
let waiting = false;
const shot = document.querySelector(".shot");
function moveLayers() {
  waiting = false;
  const scroll = window.scrollY;
  for (const { element, depth } of layers) {
    element.style.transform = `translate3d(${mouseX * depth * 40}px, ${mouseY * depth * 40 - scroll * depth}px, 0)`;
  }
  if (shot) {
    // Снимок программы выпрямляется, когда подъезжает к середине экрана.
    const top = shot.getBoundingClientRect().top / window.innerHeight;
    shot.style.setProperty("--tilt", Math.max(0, Math.min(12, top * 14)).toFixed(2) + "deg");
  }
}
function requestMove() {
  if (!waiting) {
    waiting = true;
    requestAnimationFrame(moveLayers);
  }
}
if (!still) {
  window.addEventListener("scroll", requestMove, { passive: true });
  window.addEventListener("pointermove", (event) => {
    mouseX = event.clientX / window.innerWidth - 0.5;
    mouseY = event.clientY / window.innerHeight - 0.5;
    requestMove();
  }, { passive: true });
  requestMove();

  // Свет внутри карточки следует за мышью.
  document.querySelectorAll(".cards li, .mod").forEach((card) => {
    card.addEventListener("pointermove", (event) => {
      const box = card.getBoundingClientRect();
      card.style.setProperty("--x", event.clientX - box.left + "px");
      card.style.setProperty("--y", event.clientY - box.top + "px");
    });
  });
}
