if ('serviceWorker' in navigator && window.isSecureContext) {
  navigator.serviceWorker.register('/service-worker.js').catch(error => console.warn('Offline notice unavailable', error));
}
