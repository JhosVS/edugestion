// Colapsar / expandir el menú lateral. Solo cambia clases visuales del <body>.
// - Escritorio (>= 1100 px): alterna el menú reducido a íconos y recuerda la elección.
// - Pantallas medianas: el menú ya está reducido; el botón lo abre encima del contenido.
(() => {
  const boton = document.getElementById("alternar-menu");
  if (!boton) return;
  const ancho = window.matchMedia("(min-width: 1100px)");
  const cuerpo = document.body;

  try {
    if (localStorage.getItem("menu-mini") === "1") cuerpo.classList.add("menu-mini");
  } catch (e) { /* sin almacenamiento: se usa el menú completo */ }

  const cerrar = () => cuerpo.classList.remove("menu-abierto");

  boton.addEventListener("click", () => {
    if (ancho.matches) {
      const mini = cuerpo.classList.toggle("menu-mini");
      try { localStorage.setItem("menu-mini", mini ? "1" : "0"); } catch (e) { /* ignorar */ }
    } else {
      cuerpo.classList.toggle("menu-abierto");
    }
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") cerrar(); });
  document.addEventListener("click", (e) => {
    if (cuerpo.classList.contains("menu-abierto") && !e.target.closest("#sidebar, #alternar-menu")) cerrar();
  });
  ancho.addEventListener("change", cerrar);
})();
