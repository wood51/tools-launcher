const API = 'https://api.github.com/repos/wood51/tools-launcher/releases/latest';
const expectedBase = 'https://github.com/wood51/tools-launcher/releases/download/';

function validAsset(release, name) {
  return release.assets?.find(asset => asset.name === name && asset.browser_download_url?.startsWith(expectedBase));
}

function enableDownload(element, asset) {
  element.href = asset.browser_download_url;
  element.removeAttribute('aria-disabled');
  element.removeAttribute('tabindex');
  element.classList.remove('unavailable');
}

async function refreshRelease() {
  const status = document.getElementById('release-status');
  try {
    const response = await fetch(API, {headers: {'Accept': 'application/vnd.github+json'}});
    if (!response.ok) throw new Error('release unavailable');
    const release = await response.json();
    const launcher = validAsset(release, 'ToolsLauncher.zip');
    const skill = validAsset(release, 'new-extension.zip');
    if (!launcher) {
      status.textContent = 'La nouvelle installation vierge est en préparation. Le guide est déjà disponible pour la découvrir.';
      return;
    }
    enableDownload(document.getElementById('download-launcher'), launcher);
    if (skill) enableDownload(document.getElementById('download-skill'), skill);
    status.textContent = `${release.tag_name} · Installation vierge · Le téléchargement démarre directement.`;
  } catch {
    status.textContent = 'Le téléchargement ne peut pas être vérifié pour le moment. Consultez le guide ou réessayez dans quelques instants.';
  }
}

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
refreshRelease();
