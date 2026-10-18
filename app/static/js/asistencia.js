// Marca a todos los alumnos como presentes (luego se corrigen los T y F).
document.getElementById("todos-p").addEventListener("click", () => {
    document.querySelectorAll('input[type="radio"][value="P"]').forEach((r) => (r.checked = true));
});