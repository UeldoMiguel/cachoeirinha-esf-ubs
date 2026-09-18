/* Mapa Territorial da Saúde — Cachoeirinha/RS
 *
 * Aplicação estática: carrega os GeoJSON de data/ e monta as camadas no Leaflet.
 * Sem build, sem framework, sem backend. Para trocar os dados por outros —
 * inclusive pelos limites oficiais — basta substituir os arquivos em data/
 * mantendo os nomes; nada aqui precisa mudar.
 *
 * Propriedades lidas de cada feição (todas opcionais, o que faltar é omitido):
 *   polígonos : nome, unidade, tipo, codigo, descricao, ruas_cadastradas, ruas[],
 *               telefone, email, fonte
 *   pontos    : nome, tipo, codigo, telefone, email, endereco, equipe,
 *               territorio, informacoes, fonte
 */
(function () {
  'use strict';

  /* Configuração ---------------------------------------------------------- */

  var CENTRO = [-29.9509, -51.0939];   // centro aproximado de Cachoeirinha/RS
  var ZOOM = 13;
  var LIMITES_MAPA = [[-30.02, -51.20], [-29.85, -51.00]];

  var CORES = {
    ESF: '#0d7a63',
    UBS: '#2f4c8c',
    outro: '#6b5b95',
    limite: '#8a5a2b'
  };

  /* Arquivos de dados. Acrescentar uma camada é acrescentar uma linha aqui. */
  var FONTES = [
    { id: 'esf', arquivo: 'data/esf.geojson', rotulo: 'Áreas de ESF', especie: 'area', tipo: 'ESF' },
    { id: 'ubs', arquivo: 'data/ubs.geojson', rotulo: 'Áreas de UBS', especie: 'area', tipo: 'UBS' },
    { id: 'unidades', arquivo: 'data/unidades.geojson', rotulo: 'Unidades de saúde', especie: 'ponto' },
    { id: 'limite', arquivo: 'data/limite.geojson', rotulo: 'Limite do município', especie: 'limite' }
  ];

  /* Rótulos amigáveis das propriedades, na ordem em que aparecem no popup */
  var CAMPOS = [
    ['unidade', 'Unidade de referência'],
    ['tipo', 'Tipo'],
    ['codigo', 'Código'],
    ['descricao', 'Descrição'],
    ['equipe', 'Equipe'],
    ['territorio', 'Território'],
    ['endereco', 'Endereço'],
    ['telefone', 'Telefone'],
    ['email', 'E-mail'],
    ['ruas_cadastradas', 'Vias cadastradas'],
    ['informacoes', 'Informações'],
    ['fonte', 'Fonte']
  ];
  var OCULTOS = ['nome', 'ruas', 'tem_area'];

  /* Utilidades ------------------------------------------------------------ */

  function esc(v) {
    return String(v).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function semAcento(s) {
    return String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  }

  function rotuloDe(chave) {
    for (var i = 0; i < CAMPOS.length; i++) if (CAMPOS[i][0] === chave) return CAMPOS[i][1];
    return chave.charAt(0).toUpperCase() + chave.slice(1).replace(/_/g, ' ');
  }

  /* Monta <dl> com o que a feição realmente tem — nada é preenchido por suposição */
  function listaDeDados(props) {
    var usados = {}, html = '';
    CAMPOS.forEach(function (par) {
      var v = props[par[0]];
      if (v === undefined || v === null || v === '') return;
      usados[par[0]] = true;
      html += '<dt>' + esc(par[1]) + '</dt><dd>' + esc(v) + '</dd>';
    });
    Object.keys(props).forEach(function (k) {
      if (usados[k] || OCULTOS.indexOf(k) >= 0) return;
      var v = props[k];
      if (v === undefined || v === null || v === '' || typeof v === 'object') return;
      html += '<dt>' + esc(rotuloDe(k)) + '</dt><dd>' + esc(v) + '</dd>';
    });
    return html ? '<dl>' + html + '</dl>' : '';
  }

  function classeMarca(tipo) {
    return tipo === 'ESF' || tipo === 'UBS' ? 'marca-' + tipo : 'marca-outro';
  }

  function corDe(tipo) {
    return CORES[tipo] || CORES.outro;
  }

  function conteudoPopup(props) {
    var t = props.tipo || '';
    return '<div class="pop">' +
      (t ? '<span class="marca ' + classeMarca(t) + '">' + esc(t) + '</span>' : '') +
      '<h3>' + esc(props.nome || props.unidade || 'Sem nome') + '</h3>' +
      listaDeDados(props) +
      '</div>';
  }

  /* Mapa ------------------------------------------------------------------ */

  var mapa = L.map('mapa', {
    center: CENTRO,
    zoom: ZOOM,
    minZoom: 11,
    maxZoom: 18,
    maxBounds: LIMITES_MAPA,
    maxBoundsViscosity: .6,
    zoomControl: true,
    scrollWheelZoom: true
  });

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(mapa);

  L.control.scale({ imperial: false, metric: true }).addTo(mapa);

  var camadas = {};      // id -> L.LayerGroup
  var itensBusca = [];   // {nome, tipo, camada, alvo}

  /* Estilos e comportamento por espécie de camada ------------------------- */

  function estiloArea(tipo) {
    return { color: corDe(tipo), weight: 2, opacity: .9, fillColor: corDe(tipo), fillOpacity: .18 };
  }

  function ligaArea(feature, layer, tipo) {
    var props = feature.properties || {};
    layer.setStyle(estiloArea(tipo));
    layer.bindPopup(conteudoPopup(props), { maxWidth: 320 });
    layer.bindTooltip(props.nome || props.unidade || '', { sticky: true });

    layer.on('mouseover', function () {
      layer.setStyle({ weight: 4, fillOpacity: .34 });
      if (layer.bringToFront) layer.bringToFront();
    });
    layer.on('mouseout', function () { layer.setStyle(estiloArea(tipo)); });
    layer.on('click', function () { mostrarDetalhe(props, layer); });
  }

  /* Teclado: só depois de a camada entrar no mapa é que existe o <path> do SVG */
  function acessibilidade(camada) {
    camada.eachLayer(function (layer) {
      var el = layer.getElement && layer.getElement();
      if (!el) return;
      var props = (layer.feature && layer.feature.properties) || {};
      el.setAttribute('tabindex', '0');
      el.setAttribute('role', 'button');
      el.setAttribute('aria-label', props.nome || props.unidade || 'Feição do mapa');
      el.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          layer.openPopup();
          mostrarDetalhe(props, layer);
        }
      });
    });
  }

  function marcadorPonto(feature, latlng) {
    var props = feature.properties || {};
    return L.circleMarker(latlng, {
      radius: 7,
      color: corDe(props.tipo),
      weight: 3,
      fillColor: '#ffffff',
      fillOpacity: 1
    });
  }

  function ligaPonto(feature, layer) {
    var props = feature.properties || {};
    layer.bindPopup(conteudoPopup(props), { maxWidth: 320 });
    layer.bindTooltip(props.nome || '', { direction: 'top' });
    layer.on('click', function () { mostrarDetalhe(props, layer); });
  }

  /* Painel lateral -------------------------------------------------------- */

  var elDetalhe = document.getElementById('detalhe');

  function mostrarDetalhe(props, layer) {
    var dados = listaDeDados(props);
    var ruas = Array.isArray(props.ruas) && props.ruas.length
      ? '<dt>Vias na abrangência (' + props.ruas.length + ')</dt>' +
        '<dd class="ruas">' + esc(props.ruas.join(' · ')) + '</dd>'
      : '';
    if (ruas) {
      dados = dados ? dados.replace('</dl>', ruas + '</dl>') : '<dl>' + ruas + '</dl>';
    }
    elDetalhe.innerHTML =
      '<h3>' + esc(props.nome || props.unidade || 'Seleção') + '</h3>' +
      (dados || '<p class="vazio">Esta feição não traz atributos.</p>');
    if (layer && layer.getBounds) mapa.fitBounds(layer.getBounds(), { padding: [30, 30] });
    else if (layer && layer.getLatLng) mapa.setView(layer.getLatLng(), Math.max(mapa.getZoom(), 16));
  }

  /* Controle de camadas próprio (o do Leaflet não acompanha o painel) ------ */

  var elCamadas = document.getElementById('camadas');

  function criaControleCamada(fonte, grupo, quantidade) {
    var li = document.createElement('li');
    var id = 'cam-' + fonte.id;
    li.innerHTML =
      '<label for="' + id + '"><input type="checkbox" id="' + id + '" checked>' +
      '<span>' + esc(fonte.rotulo) + '</span>' +
      '<span class="contagem">(' + quantidade + ')</span></label>';
    var input = li.querySelector('input');
    input.addEventListener('change', function () {
      if (input.checked) grupo.addTo(mapa); else mapa.removeLayer(grupo);
    });
    elCamadas.appendChild(li);
  }

  /* Busca ----------------------------------------------------------------- */

  var elBusca = document.getElementById('busca');
  var elResultados = document.getElementById('resultados');

  function pintaResultados(termo) {
    var q = semAcento(termo).trim();
    elResultados.innerHTML = '';
    if (q.length < 2) return;
    var achados = itensBusca.filter(function (it) {
      return semAcento(it.nome).indexOf(q) >= 0;
    }).slice(0, 12);
    if (!achados.length) {
      elResultados.innerHTML = '<li class="dica">Nada encontrado com esse nome.</li>';
      return;
    }
    achados.forEach(function (it) {
      var li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.innerHTML = '<button type="button"><span>' + esc(it.nome) + '</span>' +
        '<span class="marca ' + classeMarca(it.tipo) + '">' + esc(it.tipo || 'serviço') + '</span></button>';
      li.querySelector('button').addEventListener('click', function () {
        if (!mapa.hasLayer(it.grupo)) {
          it.grupo.addTo(mapa);
          var cx = document.getElementById('cam-' + it.fonteId);
          if (cx) cx.checked = true;
        }
        it.alvo.openPopup();
        mostrarDetalhe(it.props, it.alvo);
      });
      elResultados.appendChild(li);
    });
  }

  elBusca.addEventListener('input', function () { pintaResultados(elBusca.value); });
  elBusca.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') { elBusca.value = ''; elResultados.innerHTML = ''; }
    if (ev.key === 'Enter') {
      var b = elResultados.querySelector('button');
      if (b) { ev.preventDefault(); b.click(); }
    }
  });

  /* Carregamento ---------------------------------------------------------- */

  function carrega(fonte) {
    return fetch(fonte.arquivo)
      .then(function (r) {
        if (!r.ok) throw new Error(fonte.arquivo + ': HTTP ' + r.status);
        return r.json();
      })
      .then(function (gj) {
        var camada;
        if (fonte.especie === 'area') {
          camada = L.geoJSON(gj, {
            style: estiloArea(fonte.tipo),
            onEachFeature: function (f, l) { ligaArea(f, l, fonte.tipo); }
          });
        } else if (fonte.especie === 'ponto') {
          camada = L.geoJSON(gj, {
            pointToLayer: marcadorPonto,
            onEachFeature: ligaPonto
          });
        } else {
          camada = L.geoJSON(gj, {
            style: { color: CORES.limite, weight: 2, dashArray: '6 5', fill: false },
            interactive: false
          });
        }
        camada.addTo(mapa);
        if (fonte.especie === 'area') acessibilidade(camada);
        camadas[fonte.id] = camada;
        criaControleCamada(fonte, camada, (gj.features || []).length);

        if (fonte.especie !== 'limite') {
          camada.eachLayer(function (l) {
            var p = (l.feature && l.feature.properties) || {};
            itensBusca.push({
              nome: p.nome || p.unidade || '',
              tipo: p.tipo || '',
              grupo: camada,
              fonteId: fonte.id,
              alvo: l,
              props: p
            });
          });
        }
        return camada;
      })
      .catch(function (e) {
        var li = document.createElement('li');
        li.className = 'dica';
        li.textContent = 'Não foi possível carregar ' + fonte.arquivo + '.';
        elCamadas.appendChild(li);
        if (window.console) console.error(e);
        return null;
      });
  }

  Promise.all(FONTES.map(carrega)).then(function (feitas) {
    var validas = feitas.filter(Boolean);
    if (!validas.length) return;
    var caixa = null;
    validas.forEach(function (c) {
      var b = c.getBounds && c.getBounds();
      if (b && b.isValid()) caixa = caixa ? caixa.extend(b) : b;
    });
    if (caixa) mapa.fitBounds(caixa, { padding: [20, 20] });
    itensBusca.sort(function (a, b) { return a.nome.localeCompare(b.nome, 'pt-BR'); });
  });

  /* Procedência ----------------------------------------------------------- */

  fetch('data/metadados.json')
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (m) {
      var el = document.getElementById('procedencia');
      if (!m) { el.textContent = 'Metadados não encontrados em data/metadados.json.'; return; }
      el.textContent = m.aviso + ' Áreas e unidades: ' + m.fontes.areas_e_unidades +
        ' Limite municipal: ' + m.fontes.limite_municipal + ' Geração dos arquivos: ' + m.gerado_em + '.';
    })
    .catch(function () {});
})();
