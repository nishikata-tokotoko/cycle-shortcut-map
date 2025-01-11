document.addEventListener("DOMContentLoaded", () => {
  fetch("header.html")
      .then(response => {
          if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
          }
          return response.text();
      })
      .then(data => {
          document.getElementById("header-placeholder").innerHTML = data;
      })
      .then(() => {
          // Responsive toggle menu
          const toggleButton = document.getElementById('menu-toggle');
          const navbarMenu = document.querySelector('.navbar-menu');
          
          if (toggleButton && navbarMenu) { // Check if elements exist
              toggleButton.addEventListener('click', () => {
                  navbarMenu.classList.toggle('active');
              });
          } else {
              console.warn("Menu toggle or navbar menu not found in the loaded header.");
          }
      })
      .catch(error => console.error("Error loading navbar:", error));
});
