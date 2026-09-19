/* Modo claro / escuro.
 *
 * Três estados: "sistema" (nada gravado, vale o prefers-color-scheme), "claro"
 * e "escuro" — escolha manual gravada em localStorage e refletida no atributo
 * data-tema da raiz, que é o que a folha de estilos observa.
 *
 * Este arquivo é carregado ANTES do mapa e do resto do CSS pintar, para a
 * página não piscar branca antes de assumir o tema escuro.
 */
(function () {
  'use strict';

  var CHAVE = 'cachoeirinha-tema';
  var raiz = document.documentElement;

  function gravado() {
    try { return localStorage.getItem(CHAVE); } catch (e) { return null; }
  }

  function sistemaEscuro() {
    return !!(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }

  function estaEscuro() {
    var t = raiz.getAttribute('data-tema');
    return t ? t === 'escuro' : sistemaEscuro();
  }

  /* Aplicado imediatamente, antes da primeira pintura */
  var inicial = gravado();
  if (inicial === 'escuro' || inicial === 'claro') raiz.setAttribute('data-tema', inicial);

  function sincronizaBotao() {
    var botao = document.getElementById('tema');
    if (!botao) return;
    var escuro = estaEscuro();
    botao.setAttribute('aria-pressed', escuro ? 'true' : 'false');
    botao.setAttribute('aria-label', escuro ? 'Mudar para o modo claro' : 'Mudar para o modo escuro');
    var icone = document.getElementById('tema-icone');
    var texto = document.getElementById('tema-texto');
    if (icone) icone.textContent = escuro ? '☀' : '◐';
    if (texto) texto.textContent = escuro ? 'Modo claro' : 'Modo escuro';
  }

  function aplica(escuro, gravar) {
    raiz.setAttribute('data-tema', escuro ? 'escuro' : 'claro');
    if (gravar) {
      try { localStorage.setItem(CHAVE, escuro ? 'escuro' : 'claro'); } catch (e) { /* modo privado */ }
    }
    sincronizaBotao();
    if (window.MapaSaude && window.MapaSaude.aplicarTemaMapa) {
      window.MapaSaude.aplicarTemaMapa(escuro);
    }
  }

  function liga() {
    sincronizaBotao();
    var botao = document.getElementById('tema');
    if (botao) {
      botao.addEventListener('click', function () { aplica(!estaEscuro(), true); });
    }
    /* Sem escolha manual, a página acompanha o sistema em tempo real */
    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      var aoMudar = function () {
        if (gravado()) return;
        raiz.removeAttribute('data-tema');
        sincronizaBotao();
        if (window.MapaSaude && window.MapaSaude.aplicarTemaMapa) {
          window.MapaSaude.aplicarTemaMapa(sistemaEscuro());
        }
      };
      if (mq.addEventListener) mq.addEventListener('change', aoMudar);
      else if (mq.addListener) mq.addListener(aoMudar);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', liga);
  else liga();
})();
