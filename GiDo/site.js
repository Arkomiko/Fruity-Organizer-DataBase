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

// Закрывает список языков при щелчке мимо него.
document.addEventListener("click", (event) => {
  const menu = document.querySelector(".langs[open]");
  if (menu && !menu.contains(event.target)) {
    menu.removeAttribute("open");
  }
});
