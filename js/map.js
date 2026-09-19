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

  /* O que a caixa mostra, nesta ordem. Só isto: o resto das propriedades do
     GeoJSON fica fora da interface para a leitura ser rápida em campo. */
  var CAMPOS = [
    ['unidade', 'Unidade de referência'],
    ['tipo', 'Tipo'],
    ['telefone', 'Telefone'],
    ['email', 'E-mail']
  ];

  /* Utilidades ------------------------------------------------------------ */

  function esc(v) {
    return String(v).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  function semAcento(s) {
    return String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  /* Monta <dl> com o que a feição realmente tem — campo ausente não aparece,
     e nada é preenchido por suposição. */
  function listaDeDados(props) {
    var html = '';
    CAMPOS.forEach(function (par) {
      var v = props[par[0]];
      if (v === undefined || v === null || v === '') return;
      var valor = par[0] === 'email'
        ? '<a href="mailto:' + esc(v) + '">' + esc(v) + '</a>'
        : esc(v);
      html += '<dt>' + esc(par[1]) + '</dt><dd>' + valor + '</dd>';
    });
    return html ? '<dl>' + html + '</dl>' : '';
  }

  function classeMarca(tipo) {
    return tipo === 'ESF' || tipo === 'UBS' ? 'marca-' + tipo : 'marca-outro';
  }

  var TOKEN = { ESF: '--esf', UBS: '--ubs', outro: '--outro', limite: '--limite' };

  function corDe(tipo) {
    var nome = TOKEN[tipo] || TOKEN.outro;
    var v = getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
    return v || CORES[tipo] || CORES.outro;
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

  /* Base única do OpenStreetMap. No tema escuro, a imagem dos tiles é
     invertida por CSS — os serviços de base escura prontos (CARTO, Stadia)
     exigem chave de API, e o filtro mantém a página sem dependência nova. */
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
  }).addTo(mapa);

  function aplicarTemaMapa(escuro) {
    mapa.getContainer().classList.toggle('mapa-escuro', !!escuro);
    /* os tokens de cor mudaram: repinta polígonos e marcadores */
    ['esf', 'ubs'].forEach(function (id) {
      var c = camadas[id];
      if (!c) return;
      c.eachLayer(function (l) {
        var t = ((l.feature || {}).properties || {}).tipo;
        l.setStyle(estiloArea(t));
      });
    });
    if (camadas.unidades) {
      camadas.unidades.eachLayer(function (l) {
        var p = (l.feature || {}).properties || {};
        if (l.setStyle) l.setStyle({ color: corDe(p.tipo), fillColor: corFundoMarcador() });
      });
    }
    if (camadas.limite) camadas.limite.setStyle({ color: corDe('limite') });
  }

  function corFundoMarcador() {
    return getComputedStyle(document.documentElement).getPropertyValue('--painel').trim() || '#ffffff';
  }

  L.control.scale({ imperial: false, metric: true }).addTo(mapa);

  var camadas = {};      // id -> L.LayerGroup
  var itensBusca = [];   // {nome, tipo, camada, alvo}

  aplicarTemaMapa(document.documentElement.getAttribute('data-tema') === 'escuro' ||
    (!document.documentElement.getAttribute('data-tema') &&
      window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches));

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
      fillColor: corFundoMarcador(),
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
    elDetalhe.innerHTML =
      '<h3>' + esc(props.nome || props.unidade || 'Seleção') + '</h3>' +
      (dados || '<p class="vazio">Esta feição não traz atributos.</p>');
    if (layer && layer.getBounds) mapa.fitBounds(layer.getBounds(), { padding: [30, 30] });
    else if (layer && layer.getLatLng) mapa.setView(layer.getLatLng(), Math.max(mapa.getZoom(), 16));
  }

  /* Controle de camadas próprio (o do Leaflet não acompanha o painel) ------ */

  var elCamadas = document.getElementById('camadas');
  var linhasCamada = {};

  /* As caixas nascem na ordem de FONTES; o carregamento é assíncrono e
     chegaria fora de ordem se cada uma fosse criada ao terminar o fetch. */
  FONTES.forEach(function (fonte) {
    var li = document.createElement('li');
    li.innerHTML = '<span class="contagem">' + esc(fonte.rotulo) + ' — carregando…</span>';
    elCamadas.appendChild(li);
    linhasCamada[fonte.id] = li;
  });

  function criaControleCamada(fonte, grupo, quantidade) {
    var li = linhasCamada[fonte.id] || elCamadas.appendChild(document.createElement('li'));
    var id = 'cam-' + fonte.id;
    li.innerHTML =
      '<label for="' + id + '"><input type="checkbox" id="' + id + '" checked>' +
      '<span>' + esc(fonte.rotulo) + '</span>' +
      '<span class="contagem">(' + quantidade + ')</span></label>';
    var input = li.querySelector('input');
    input.addEventListener('change', function () {
      if (input.checked) grupo.addTo(mapa); else mapa.removeLayer(grupo);
    });
  }

  /* Busca ----------------------------------------------------------------- */

  var elBusca = document.getElementById('busca');
  var elResultados = document.getElementById('resultados');

  /* Outros módulos (a consulta por endereço) registram provedores aqui:
     função que recebe o termo já normalizado e devolve
     [{ nome, tipo, marca?, escolher: function () {} }]. */
  var provedores = [];

  function itensDoMapa(q) {
    return itensBusca.filter(function (it) {
      return semAcento(it.nome).indexOf(q) >= 0;
    }).slice(0, 8).map(function (it) {
      return {
        nome: it.nome,
        tipo: it.tipo,
        escolher: function () {
          if (!mapa.hasLayer(it.grupo)) {
            it.grupo.addTo(mapa);
            var cx = document.getElementById('cam-' + it.fonteId);
            if (cx) cx.checked = true;
          }
          it.alvo.openPopup();
          mostrarDetalhe(it.props, it.alvo);
        }
      };
    });
  }

  function pintaResultados(termo) {
    var q = semAcento(termo).trim();
    elResultados.innerHTML = '';
    if (q.length < 2) return;

    var achados = itensDoMapa(q);
    provedores.forEach(function (p) {
      try { achados = achados.concat(p(q, termo) || []); } catch (e) { /* provedor falho não derruba a busca */ }
    });
    achados = achados.slice(0, 12);

    if (!achados.length) {
      elResultados.innerHTML = '<li class="dica">Nada encontrado com esse nome.</li>';
      return;
    }
    achados.forEach(function (it) {
      var li = document.createElement('li');
      li.setAttribute('role', 'option');
      li.innerHTML = '<button type="button"><span>' + esc(it.nome) + '</span>' +
        '<span class="marca ' + classeMarca(it.tipo) + '">' +
        esc(it.marca || it.tipo || 'serviço') + '</span></button>';
      li.querySelector('button').addEventListener('click', function () {
        elResultados.innerHTML = '';
        it.escolher();
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
        var li = linhasCamada[fonte.id];
        if (li) {
          li.className = 'dica';
          li.textContent = 'Não foi possível carregar ' + fonte.arquivo + '.';
        }
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

  /* API para os outros módulos da página ---------------------------------- */

  window.MapaSaude = {
    mapa: mapa,
    aplicarTemaMapa: aplicarTemaMapa,
    cores: CORES,
    esc: esc,
    semAcento: semAcento,
    classeMarca: classeMarca,
    mostrarDetalhe: mostrarDetalhe,
    /* registra um provedor de resultados na caixa de busca */
    registrarBusca: function (fn) { provedores.push(fn); },
    /* devolve a camada do polígono cujo properties.codigo bate, ou null */
    poligonoPorCodigo: function (codigo) {
      var achou = null;
      ['esf', 'ubs'].forEach(function (id) {
        var c = camadas[id];
        if (!c || achou) return;
        c.eachLayer(function (l) {
          var p = (l.feature && l.feature.properties) || {};
          if (!achou && p.codigo === codigo) achou = l;
        });
      });
      return achou;
    },
    /* unidades de um tipo ('ESF', 'UBS'…) como [{props, latlng}] */
    unidadesPorTipo: function (tipo) {
      var saida = [];
      var c = camadas.unidades;
      if (!c) return saida;
      c.eachLayer(function (l) {
        var p = (l.feature && l.feature.properties) || {};
        if (!tipo || p.tipo === tipo) saida.push({ props: p, latlng: l.getLatLng(), camada: l });
      });
      return saida;
    },
    /* garante que a camada esteja visível e sincroniza a caixinha */
    mostrarCamada: function (id) {
      var c = camadas[id];
      if (c && !mapa.hasLayer(c)) {
        c.addTo(mapa);
        var cx = document.getElementById('cam-' + id);
        if (cx) cx.checked = true;
      }
    }
  };

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
