// Faixa "Instale o 9Self" (igual à do PsiCoWorking): aparece sozinha quando o aparelho permite instalar.
// Android/Chrome e computador: abre a instalação direto. iPhone: mostra os passos do Safari.
// Se a pessoa já instalou ou fechou a faixa, ela não aparece de novo.
(function () {
  try {
    var FLAG_INSTALADO = "nineself_app_instalado";
    var CHAVE = "nineself_instalar_fechado";
    function lembrarInstalado() { try { localStorage.setItem(FLAG_INSTALADO, "1"); } catch (e) {} }
    var jaInstalado = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
    if (jaInstalado) { lembrarInstalado(); return; }
    try { if (localStorage.getItem(FLAG_INSTALADO) === "1") return; } catch (e) {}
    try { if (localStorage.getItem(CHAVE) === "1") return; } catch (e) {}
    // não repete a faixa dentro da própria página de instruções
    if (/instalar-app\.html/.test(location.pathname)) return;

    var base = document.currentScript ? new URL(".", document.currentScript.src).href : location.href;
    var icone = new URL("marca/icone-192.png", base).href;

    var ios = /iphone|ipad|ipod/i.test(navigator.userAgent);
    var pedido = null;
    var faixa = null;

    function css() {
      var s = document.createElement("style");
      s.textContent =
        ".nself-inst{position:fixed;left:12px;right:12px;bottom:12px;z-index:99999;max-width:460px;margin:0 auto;background:#39044F;color:#fff;border:1px solid rgba(240,184,81,.35);border-radius:14px;padding:12px 14px;display:flex;align-items:center;gap:12px;box-shadow:0 8px 28px rgba(0,0,0,.35);font-family:'DM Sans',system-ui,sans-serif}" +
        ".nself-inst img{width:42px;height:42px;border-radius:10px;flex:none}" +
        ".nself-inst div{flex:1;font-size:13.5px;line-height:1.35;color:#E9D6F5}" +
        ".nself-inst b{display:block;font-size:14.5px;color:#fff}" +
        ".nself-inst button{font:600 14px 'DM Sans',system-ui,sans-serif;border:0;border-radius:10px;cursor:pointer}" +
        ".nself-inst .sim{background:#F0B851;color:#39044F;padding:10px 16px}" +
        ".nself-inst .x{background:transparent;color:#E9D6F5;font-size:20px;padding:4px 8px}" +
        ".nself-inst-ajuda{position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;padding:16px}" +
        ".nself-inst-ajuda div{background:#fff;color:#1F1B2E;border-radius:16px;padding:22px;max-width:380px;font:15px/1.6 'DM Sans',system-ui,sans-serif}" +
        ".nself-inst-ajuda h3{margin:0 0 10px;font-size:18px;color:#39044F}.nself-inst-ajuda ol{margin:0 0 14px;padding-left:20px}" +
        ".nself-inst-ajuda button{background:#39044F;color:#fff;border:0;border-radius:10px;padding:10px 18px;font:600 14px 'DM Sans',sans-serif;cursor:pointer}";
      document.head.appendChild(s);
    }

    function ajuda() {
      var f = document.createElement("div");
      f.className = "nself-inst-ajuda";
      f.innerHTML = "<div><h3>Instalar o 9Self no celular</h3><ol>" +
        (ios
          ? "<li>Abra esta página no <b>Safari</b>.</li><li>Toque no botão de compartilhar (quadrado com seta para cima).</li><li>Escolha <b>Adicionar à Tela de Início</b>.</li>"
          : "<li>Toque nos <b>três pontinhos</b> do navegador.</li><li>Escolha <b>Instalar aplicativo</b> ou <b>Adicionar à tela inicial</b>.</li>") +
        "</ol><button type='button'>Entendi</button></div>";
      f.onclick = function (e) { if (e.target === f || e.target.tagName === "BUTTON") f.remove(); };
      document.body.appendChild(f);
    }

    function mostrar() {
      if (faixa || !document.body) return;
      css();
      faixa = document.createElement("div");
      faixa.className = "nself-inst";
      faixa.innerHTML = "<img src='" + icone + "' alt=''><div><b>Instale o 9Self</b>Tenha o atalho na tela do seu celular.</div>" +
        "<button type='button' class='sim'>Instalar</button><button type='button' class='x' aria-label='Fechar'>&times;</button>";
      faixa.querySelector(".sim").onclick = function () {
        if (pedido) {
          pedido.prompt();
          pedido.userChoice.then(function () { pedido = null; faixa.remove(); });
        } else ajuda();
      };
      faixa.querySelector(".x").onclick = function () {
        faixa.remove();
        try { localStorage.setItem(CHAVE, "1"); } catch (e) {}
      };
      document.body.appendChild(faixa);
    }

    var instaladoDetectado = false;
    window.addEventListener("beforeinstallprompt", function (e) { e.preventDefault(); pedido = e; if (!instaladoDetectado) mostrar(); });
    window.addEventListener("appinstalled", function () { lembrarInstalado(); if (faixa) faixa.remove(); });
    if (navigator.getInstalledRelatedApps) {
      navigator.getInstalledRelatedApps().then(function (lista) {
        if (lista && lista.length) { instaladoDetectado = true; lembrarInstalado(); if (faixa) faixa.remove(); }
      }).catch(function () {});
    }
    // Só o iPhone não avisa sozinho: ali mostramos a faixa com os passos do Safari.
    if (ios) window.addEventListener("load", function () { setTimeout(function () { if (!instaladoDetectado) mostrar(); }, 2500); });
  } catch (e) {}
})();
