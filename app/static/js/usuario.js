// Muestra sección y DNI solo cuando el rol elegido es "alumno".
const rol = document.getElementById("rol");
if (rol) {
  rol.addEventListener("change", () => {
    document.getElementById("solo-alumno").hidden = rol.value !== "alumno";
  });
}
