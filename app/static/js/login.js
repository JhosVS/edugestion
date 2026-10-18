// Rellena el formulario con las credenciales de prueba.
document.querySelectorAll(".usar-cred").forEach((boton) => {
  boton.addEventListener("click", () => {
    document.getElementById("correo").value = boton.dataset.correo;
    document.getElementById("clave").value = boton.dataset.clave;
    document.getElementById("clave").focus();
  });
});