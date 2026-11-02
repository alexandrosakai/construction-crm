// Sistema de temas (incluindo modo escuro)
const themes = {
  light: {
    background: '#ffffff',
    text: '#000000',
    // ... outras cores
  },
  dark: {
    background: '#121212',
    text: '#ffffff',
    // ... outras cores
  }
};

function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
} 