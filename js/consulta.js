/* Consulta por endereço dentro do mapa.
 *
 * Responde se uma rua (com ou sem número) é área de ESF ou de UBS, mostra a
 * unidade de referência, desenha a via em vermelho e —
 * quando há número — só o trecho da quadra com aquela numeração.
 *
 * Dados: data/consulta.json, carregado sob demanda na primeira digitação.
 *   ruas    [chave, rótulo, [codigoArea], lat, lon, sugerida, [idLinha]]
 *   linhas  polilinhas do OpenStreetMap
 *   trechos faces de quadra do CNEFE 2022 (numeração + traçado)
 *
 * Depende de window.MapaSaude, exposto por js/map.js.
 */
(function () {
  'use strict';

  var API = window.MapaSaude;
  if (!API) return;

  var ARQUIVO = 'data/consulta.json';
  var elResposta = document.getElementById('resposta');
  var elBusca = document.getElementById('busca');

  var dados = null;       // {ruas, linhas, trechos}
  var porChave = {};      // chave -> objeto de rua
  var lista = [];
  var carregando = null;

  /* Normalização de nome de via — a mesma do processamento em Python, para
     "R. 31 de Março", "Rua Trinta e Um de Março" e "rua 31 de marco" caírem
     na mesma chave. */
  var TIPOS = { rua: 1, r: 1, avenida: 1, av: 1, travessa: 1, trav: 1, tv: 1, beco: 1, bc: 1,
    estrada: 1, est: 1, praca: 1, pc: 1, alameda: 1, al: 1, rodovia: 1, rod: 1, largo: 1,
    via: 1, viela: 1, passagem: 1, linha: 1, servidao: 1, esquina: 1 };
  var ABREV = { sto: 'santo', sta: 'santa', s: 'sao', sao: 'sao', dr: 'doutor', dra: 'doutora',
    prof: 'professor', profa: 'professora', pe: 'padre', cel: 'coronel', gal: 'general',
    gen: 'general', cap: 'capitao', ten: 'tenente', sgt: 'sargento', mal: 'marechal',
    maj: 'major', eng: 'engenheiro', pres: 'presidente', vda: 'viuva', d: 'dom',
    pq: 'parque', jd: 'jardim', cj: 'conjunto', vl: 'vila' };
  var NUM = { primeiro: '1', primeira: '1', segundo: '2', segunda: '2', terceiro: '3',
    terceira: '3', um: '1', uma: '1', dois: '2', duas: '2', tres: '3', quatro: '4', cinco: '5',
    seis: '6', sete: '7', oito: '8', nove: '9', dez: '10', onze: '11', doze: '12', treze: '13',
    quatorze: '14', catorze: '14', quinze: '15', dezesseis: '16', dezessete: '17', dezoito: '18',
    dezenove: '19', vinte: '20', trinta: '30', quarenta: '40', cinquenta: '50' };
  var STOP = { de: 1, da: 1, do: 1, das: 1, dos: 1, e: 1, no: 1, na: 1 };

  function norm(s) {
    s = String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    s = s.replace(/,.*$/, ' ').replace(/\bn[º°ro]*\.?\s*\d+/g, ' ').replace(/[^a-z0-9 ]/g, ' ');
    var t = s.split(/\s+/).filter(Boolean);
    if (t.length && TIPOS[t[0]]) t = t.slice(1);
    t = t.map(function (x) { return ABREV[x] || x; }).filter(function (x) { return !STOP[x]; });
    t = t.map(function (x) { return /^\d+$/.test(x) ? String(parseInt(x, 10)) : (NUM[x] || x); });
    var o = [];
    for (var i = 0; i < t.length; i++) {
      var p = o[o.length - 1];
      if (p && /^\d+$/.test(p) && /^\d+$/.test(t[i]) && +p >= 20 && +p % 10 === 0 && +t[i] < 10) {
        o[o.length - 1] = String(+p + +t[i]);
      } else { o.push(t[i]); }
    }
    if (o.length > 2 && /^\d+$/.test(o[o.length - 1])) o.pop();
    return o.join(' ');
  }

  function numeroDigitado(txt) {
    var m = String(txt || '').match(/(?:,|\s|n[º°o]\.?)\s*(\d{1,6})\s*$/i);
    if (!m) return null;
    var n = parseInt(m[1], 10);
    return n > 0 ? n : null;
  }

  /* Distância de Manhattan: soma dos deslocamentos em latitude e longitude,
     que se aproxima do caminho por quadras — o percurso real de quem anda. */
  function km(a, b) {
    var lat = (a[0] + b[0]) / 2 * Math.PI / 180;
    var dx = Math.abs(a[1] - b[1]) * Math.cos(lat), dy = Math.abs(a[0] - b[0]);
    return (dx + dy) * 111.32;
  }

  /* Camada do desenho em vermelho ----------------------------------------- */

  var grupo = L.layerGroup().addTo(API.mapa);

  function limparDesenho() { grupo.clearLayers(); }

  function corVia() {
    return getComputedStyle(document.documentElement).getPropertyValue('--via').trim() || '#d81f26';
  }

  function desenhaLinhas(polis) {
    var cor = corVia(), caixa = null;
    polis.forEach(function (l) {
      if (!l || !l.length) return;
      var pontos = l.map(function (p) { return [p[1], p[0]]; });   // [lon,lat] -> [lat,lng]
      L.polyline(pontos, { color: '#ffffff', weight: 9, opacity: .75 }).addTo(grupo);
      var linha = L.polyline(pontos, { color: cor, weight: 5, opacity: 1 }).addTo(grupo);
      caixa = caixa ? caixa.extend(linha.getBounds()) : linha.getBounds();
    });
    return caixa;
  }

  function marcaPonto(latlng) {
    L.circleMarker(latlng, {
      radius: 8, color: '#ffffff', weight: 3, fillColor: corVia(), fillOpacity: 1
    }).addTo(grupo);
  }

  /* Trechos de quadra (CNEFE) --------------------------------------------- */

  function acharTrecho(chave, num) {
    var faces = dados.trechos[chave];
    if (!faces || !faces.length || !num) return null;
    var par = num % 2, dentro = [];
    faces.forEach(function (t) { if (num >= t[0] && num <= t[1]) dentro.push(t); });
    if (dentro.length > 1) {
      var mesmo = dentro.filter(function (t) { return t[0] % 2 === par || t[1] % 2 === par; });
      if (mesmo.length) dentro = mesmo;
    }
    if (dentro.length) return { t: dentro[0], exato: true };
    var melhor = null, dist = 1e12;
    faces.forEach(function (t) {
      var d = num < t[0] ? t[0] - num : num - t[1];
      if (d < dist) { dist = d; melhor = t; }
    });
    return (melhor && dist <= 20) ? { t: melhor, exato: false, dist: dist } : { t: null, longe: true };
  }

  function pontoNoTrecho(t, num) {
    var l = t[2];
    if (l.length < 2) return [l[0][1], l[0][0]];
    var f = t[1] > t[0] ? Math.min(1, Math.max(0, (num - t[0]) / (t[1] - t[0]))) : .5;
    var i = Math.min(l.length - 2, Math.floor(f * (l.length - 1)));
    var g = f * (l.length - 1) - i;
    return [l[i][1] + (l[i + 1][1] - l[i][1]) * g, l[i][0] + (l[i + 1][0] - l[i][0]) * g];
  }

  function noAnel(latlng, anel) {
    var x = latlng[1], y = latlng[0], dentro = false;
    for (var i = 0, j = anel.length - 1; i < anel.length; j = i++) {
      var xi = anel[i][0], yi = anel[i][1], xj = anel[j][0], yj = anel[j][1];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) dentro = !dentro;
    }
    return dentro;
  }

  /* Vale para Polygon e para MultiPolygon (área de UBS unida a outra). */
  function dentroDoPoligono(latlng, camada) {
    var g = camada.feature.geometry;
    var partes = g.type === 'MultiPolygon' ? g.coordinates : [g.coordinates];
    for (var i = 0; i < partes.length; i++) {
      if (noAnel(latlng, (partes[i] || [])[0] || [])) return true;
    }
    return false;
  }

  /* Resposta -------------------------------------------------------------- */

  var esc = API.esc;

  function linhaUnidade(props, distancia) {
    var cor = props.tipo === 'ESF' ? API.cores.ESF : props.tipo === 'UBS' ? API.cores.UBS : API.cores.outro;
    return '<li><span class="bolinha" style="background:' + cor + '"></span><span>' +
      '<span class="nm">' + esc(props.nome) + '</span>' +
      (distancia != null ? '<br><span class="dist">' + distancia.toFixed(1).replace('.', ',') +
        ' km pelas quadras</span>' : '') +
      (props.telefone ? '<br><span class="dist">' + API.linkTelefone(props.telefone) + '</span>' : '') +
      '</span></li>';
  }

  function unidadeDaArea(codigoArea) {
    var poligono = API.poligonoPorCodigo(codigoArea);
    if (!poligono) return null;
    var nomeUnidade = (poligono.feature.properties || {}).unidade;
    var achada = null;
    API.unidadesPorTipo(null).forEach(function (u) {
      if (!achada && u.props.nome === nomeUnidade) achada = u;
    });
    return { poligono: poligono, unidade: achada, props: poligono.feature.properties || {} };
  }

  var ultima = null;

  function responder(rua, num) {
    ultima = { rua: rua, num: num };
    var codigo = rua[2][0];
    var trecho = num ? acharTrecho(rua[0], num) : null;
    var alvo = null;

    /* Com número, é o trecho que decide a área — inclusive em rua de divisa */
    if (trecho && trecho.t) {
      var p = pontoNoTrecho(trecho.t, num);
      for (var i = 0; i < rua[2].length; i++) {
        var cand = API.poligonoPorCodigo(rua[2][i]);
        if (cand && dentroDoPoligono(p, cand)) { codigo = rua[2][i]; break; }
      }
      alvo = p;
    }

    var area = unidadeDaArea(codigo);
    if (!area) { elResposta.innerHTML = '<p class="dica">Área não encontrada no mapa.</p>'; return; }

    var tipo = area.props.tipo;
    var referencia = area.unidade ? area.unidade.props : { nome: area.props.unidade, tipo: tipo };
    var ponto = alvo || (rua[3] != null ? [rua[3], rua[4]] : null);
    var html = '';

    html += '<div class="veredito ' + (tipo === 'ESF' ? 'esf' : 'ubs') + '">' +
      '<p class="via">' + esc(rua[1]) + (num ? ', ' + num : '') + '</p>' +
      '<h3>' + (tipo === 'ESF' ? 'Sim — área de ESF' : 'Não — área de UBS') + '</h3>' +
      '<p>' + (tipo === 'ESF'
        ? 'Este endereço está na abrangência da <strong>' + esc(referencia.nome) +
          '</strong>, uma Estratégia Saúde da Família: equipe fixa, agente comunitário e visita domiciliar.'
        : (Array.isArray(area.props.unidades) && area.props.unidades.length > 1
          ? 'Este endereço é atendido em conjunto por <strong>' + esc(area.props.unidade) +
            '</strong>, Unidades Básicas de Saúde sem equipe de Saúde da Família vinculada.'
          : 'Este endereço está na abrangência da <strong>' + esc(referencia.nome) +
            '</strong>, uma Unidade Básica de Saúde sem equipe de Saúde da Família vinculada.')) +
      '</p></div>';

    var grupo = area.props.unidades;
    if (Array.isArray(grupo) && grupo.length) {
      html += '<p class="rotulo-ref">Unidades de referência</p><ul class="refs">' +
        grupo.map(function (g) {
          return linhaUnidade({ nome: g.nome, tipo: tipo, telefone: g.telefone }, null) +
            (g.endereco ? '<li class="dist" style="margin:-4px 0 0 19px">' + esc(g.endereco) + '</li>' : '');
        }).join('') + '</ul>';
    } else {
      html += '<p class="rotulo-ref">Unidade de referência</p><ul class="refs">' +
        linhaUnidade(referencia, ponto && area.unidade
          ? km(ponto, [area.unidade.latlng.lat, area.unidade.latlng.lng]) : null) + '</ul>';
    }

    if (num && trecho && trecho.t) {
      html += '<p class="nota">Em vermelho, só o lado de quadra da numeração ' + trecho.t[0] +
        '–' + trecho.t[1] + ' (' + trecho.t[3] + ' endereços no CNEFE 2022 do IBGE).' +
        (trecho.exato ? '' : ' O nº ' + num + ' não consta; mostrado o trecho de numeração mais próxima.') +
        '</p>';
    } else if (num && trecho && trecho.longe) {
      html += '<p class="nota">O nº ' + num + ' não aparece nesta via no CNEFE 2022 do IBGE. ' +
        'O mapa marca a via inteira e a resposta vale para a rua toda.</p>';
    } else if (num && !dados.trechos[rua[0]]) {
      html += '<p class="nota">Esta via não tem numeração cadastrada no CNEFE 2022. ' +
        'O mapa marca a via inteira.</p>';
    }

    elResposta.innerHTML = html;

    /* Desenho e enquadramento ------------------------------------------- */
    limparDesenho();
    API.mostrarCamada(tipo === 'ESF' ? 'esf' : 'ubs');
    var caixa = null;

    if (trecho && trecho.t) {
      caixa = desenhaLinhas([trecho.t[2]]);
      marcaPonto(pontoNoTrecho(trecho.t, num));
      if (caixa) API.mapa.fitBounds(caixa.pad(2.2));
    } else if (rua[6] && rua[6].length) {
      caixa = desenhaLinhas(rua[6].map(function (i) { return dados.linhas[i]; }));
      var bArea = area.poligono.getBounds();
      if (caixa) bArea = bArea.extend(caixa);
      API.mapa.fitBounds(bArea, { padding: [25, 25] });
    } else {
      if (ponto) marcaPonto(ponto);
      API.mapa.fitBounds(area.poligono.getBounds(), { padding: [25, 25] });
    }
    area.poligono.openPopup(ponto ? L.latLng(ponto[0], ponto[1]) : undefined);
  }

  /* Carga sob demanda e provedor de busca --------------------------------- */

  function carregar() {
    if (dados) return Promise.resolve(dados);
    if (carregando) return carregando;
    carregando = fetch(ARQUIVO)
      .then(function (r) {
        if (!r.ok) throw new Error(ARQUIVO + ': HTTP ' + r.status);
        return r.json();
      })
      .then(function (j) {
        dados = j;
        j.ruas.forEach(function (r) { porChave[r[0]] = r; lista.push(r); });
        return j;
      })
      .catch(function (e) {
        if (window.console) console.error(e);
        elResposta.innerHTML = '<p class="dica">Não foi possível carregar a base de ruas ' +
          '(' + esc(ARQUIVO) + '). A busca por unidade e área continua funcionando.</p>';
        return null;
      });
    return carregando;
  }

  function ranquear(q) {
    var achados = [];
    for (var i = 0; i < lista.length && achados.length < 60; i++) {
      var k = lista[i][0], nota = -1;
      if (k === q) nota = 100;
      else if (k.indexOf(q) === 0) nota = 80;
      else if (k.indexOf(q) > 0) nota = 60;
      if (nota > 0) achados.push({ r: lista[i], nota: nota });
    }
    achados.sort(function (a, b) {
      return b.nota - a.nota || a.r[1].localeCompare(b.r[1], 'pt-BR');
    });
    return achados.slice(0, 6).map(function (x) { return x.r; });
  }

  API.registrarBusca(function (q, termoOriginal) {
    if (!dados) { carregar().then(function () { /* a próxima digitação já acha */ }); return []; }
    var chave = norm(termoOriginal);
    var num = numeroDigitado(termoOriginal);
    var candidatas = ranquear(chave || q);
    return candidatas.map(function (r) {
      /* "Acesso 05" é o nome da via, não a via "Acesso" no número 5 */
      var partes = r[0].split(' ');
      var numDaVia = (num && partes[partes.length - 1] === String(num)) ? null : num;
      return {
        nome: r[1] + (numDaVia ? ', ' + numDaVia : ''),
        tipo: (r[2][0] || '').indexOf('ESF') === 0 ? 'ESF' : 'UBS',
        marca: r[5] ? 'via sugerida' : 'via',
        escolher: function () {
          elBusca.value = r[1] + (numDaVia ? ', ' + numDaVia : '');
          responder(r, numDaVia);
        }
      };
    });
  });

  /* Primeira digitação dispara a carga; Enter responde direto se houver
     uma única via compatível. */
  elBusca.addEventListener('input', function () {
    if (!dados && elBusca.value.trim().length >= 2) {
      carregar().then(function () { elBusca.dispatchEvent(new Event('input')); });
    }
    if (!elBusca.value.trim()) { elResposta.innerHTML = ''; limparDesenho(); }
  });

  /* Trocar entre médico/enfermeiro e dentista refaz a resposta, porque o
     território de UBS pode ser outro. */
  API.aoTrocarModo = function () {
    if (!ultima || !dados) return;
    responder(ultima.rua, ultima.num);
  };

  /* O vermelho tem tom diferente em cada tema: redesenha ao trocar */
  if (window.MutationObserver) {
    new MutationObserver(function () {
      grupo.eachLayer(function (l) {
        if (l.setStyle && l.options.weight === 5) l.setStyle({ color: corVia() });
        if (l.setStyle && l.options.fillOpacity === 1) l.setStyle({ fillColor: corVia() });
      });
    }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-tema'] });
  }
})();
