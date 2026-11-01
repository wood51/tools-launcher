document.getElementById('copy-prompt').addEventListener('click', async () => {
  const text = 'Je voudrais un outil Tools Launcher pour classer mes fichiers et retrouver rapidement les dossiers dont j’ai besoin. Aide-moi à préciser les fonctionnalités, puis propose une première version simple.';
  const status = document.getElementById('copy-status');
  try {
    await navigator.clipboard.writeText(text);
    status.textContent = 'Exemple copié. Collez-le dans votre assistant avec le skill.';
  } catch {
    status.textContent = 'Sélectionnez puis copiez l’exemple affiché ci-dessus.';
  }
});
