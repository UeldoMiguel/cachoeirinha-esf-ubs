# Mapa Territorial da Saúde — Cachoeirinha/RS

Aplicação web estática que mostra, sobre o mapa de Cachoeirinha/RS, a divisão territorial das áreas de **ESF** (Estratégia Saúde da Família) e **UBS** (Unidades Básicas de Saúde), a localização das unidades de saúde e qual unidade atende cada território.

**Publicação:** https://ueldomiguel.github.io/cachoeirinha-esf-ubs/

Duas páginas compõem o projeto:

| Página | Para quê |
|---|---|
| [`index.html`](index.html) | Mapa interativo com camadas, legenda, busca, popups e painel de detalhes. Lê os GeoJSON de `data/`. |
| [`consulta/index.html`](consulta/index.html) | Consulta por endereço: digita-se a rua (com número, se houver) e a página responde se o endereço é área de ESF ou de UBS, com a unidade de referência e a ESF mais próxima. Arquivo único, com os dados embutidos. |

> **Aviso sobre os dados.** Os limites territoriais aqui publicados foram digitalizados de mapa colaborativo público e servem como dado de trabalho. **Não substituem o cadastro oficial** da Secretaria Municipal de Saúde de Cachoeirinha. Os limites oficiais devem ser fornecidos pela fonte responsável e substituídos nos arquivos de `data/` (veja abaixo) — a aplicação não precisa de nenhuma alteração para passar a usá-los.

## 1. Objetivo

Dar a gestores, equipes e à população uma forma direta de responder a duas perguntas:

1. **Qual é o território de cada unidade?** — polígonos de ESF e UBS desenhados sobre o mapa, com legenda e controle de camadas.
2. **Qual unidade atende este endereço?** — busca por nome de unidade/área no mapa, e busca por rua e número na página de consulta.

## 2. Tecnologias

- HTML, CSS e JavaScript puros, sem framework e sem etapa de build para publicar.
- [Leaflet 1.9.4](https://leafletjs.com/) via CDN (unpkg), com camada-base do OpenStreetMap.
- GeoJSON (RFC 7946) como formato de dados.
- GitHub Pages para hospedagem.
- Python 3 (biblioteca padrão) apenas para *regerar* os dados — não é necessário para usar ou publicar o site.

## 3. Estrutura dos arquivos

```
cachoeirinha-esf-ubs/
├── index.html              aplicação do mapa
├── css/style.css           estilos (tokens de cor no :root)
├── js/map.js               carga dos GeoJSON, camadas, popups, busca
├── data/                   dados publicados, consumidos pelo navegador
│   ├── esf.geojson         polígonos das áreas de ESF
│   ├── ubs.geojson         polígonos das áreas de UBS
│   ├── unidades.geojson    pontos das unidades e serviços
│   ├── limite.geojson      contorno do município (OpenStreetMap)
│   └── metadados.json      procedência, data de geração e contagens
├── assets/favicon.svg
├── consulta/index.html     página de consulta por endereço (arquivo único)
├── scripts/                geração dos dados (Python) — não roda no navegador
├── dados/                  fontes e intermediários do processamento
├── dist/artifact.html      variante da consulta para publicação como Artifact
├── ruas-nao-contempladas.csv
├── .nojekyll               evita o processamento Jekyll no GitHub Pages
├── LICENSE                 MIT para o código; licenças dos dados descritas nele
└── README.md
```

Todos os caminhos no HTML, CSS e JS são **relativos** (`css/style.css`, `data/esf.geojson`), como exige a publicação em subdiretório do `github.io`.

## 4. Como adicionar ou substituir arquivos GeoJSON

A troca de dados é feita **sem tocar no código**:

1. Coloque o arquivo em `data/` com um dos nomes já usados (`esf.geojson`, `ubs.geojson`, `unidades.geojson`, `limite.geojson`) para substituir uma camada existente.
2. Para acrescentar uma camada nova, adicione o arquivo em `data/` e uma linha na lista `FONTES`, no começo de [`js/map.js`](js/map.js):

```javascript
var FONTES = [
  { id: 'esf',  arquivo: 'data/esf.geojson',  rotulo: 'Áreas de ESF', especie: 'area', tipo: 'ESF' },
  { id: 'ubs',  arquivo: 'data/ubs.geojson',  rotulo: 'Áreas de UBS', especie: 'area', tipo: 'UBS' },
  { id: 'unidades', arquivo: 'data/unidades.geojson', rotulo: 'Unidades de saúde', especie: 'ponto' },
  { id: 'limite',   arquivo: 'data/limite.geojson',   rotulo: 'Limite do município', especie: 'limite' }
  // nova camada:
  // { id: 'microareas', arquivo: 'data/microareas.geojson', rotulo: 'Microáreas', especie: 'area', tipo: 'ESF' }
];
```

`especie` aceita `area` (polígonos clicáveis, com destaque no hover), `ponto` (marcadores) e `limite` (linha de contorno, não clicável). A camada nova ganha automaticamente caixa no controle de camadas, entrada na busca e popup.

3. Faça commit e envie: o GitHub Pages republica sozinho em cerca de um minuto.

**Coordenadas em EPSG:4326** (longitude, latitude), como manda a RFC 7946. Se o dado oficial vier em SIRGAS 2000 / UTM, converta antes (QGIS: *Exportar → Salvar feições como… → GeoJSON → SRC EPSG:4326*).

## 5. Estrutura esperada dos GeoJSON

Propriedades genéricas; **o que não existir é simplesmente omitido** — a aplicação nunca preenche campo ausente:

```json
{
  "type": "Feature",
  "properties": {
    "nome": "Área da ESF Canarinho",
    "unidade": "ESF Canarinho",
    "tipo": "ESF",
    "codigo": "ESF-CANARINHO",
    "descricao": "Território de abrangência da ESF Canarinho",
    "equipe": "Equipe 3",
    "territorio": "Canarinho / Vila Anair",
    "telefone": "(51) 3041-0000",
    "email": "esf.canarinho@cachoeirinha.rs.gov.br",
    "ruas": ["Rua A", "Rua B"]
  },
  "geometry": { "type": "Polygon", "coordinates": [[[-51.09, -29.95], [-51.08, -29.95], [-51.08, -29.94], [-51.09, -29.95]]] }
}
```

- `tipo` controla a cor: `ESF` (verde), `UBS` (azul), qualquer outro valor cai na cor de "outros serviços".
- `ruas` (lista) aparece no painel lateral como as vias da abrangência.
- Qualquer propriedade extra é exibida no popup com o nome do campo — não é preciso declará-la em lugar nenhum.

## 6. Como adicionar novas unidades

Acrescente uma feição de ponto em `data/unidades.geojson`:

```json
{
  "type": "Feature",
  "properties": {
    "nome": "ESF Nome da Unidade",
    "tipo": "ESF",
    "codigo": "ESF-NOME-DA-UNIDADE",
    "endereco": "Rua Exemplo, 100 — Bairro",
    "telefone": "(51) 3041-0000",
    "equipe": "Equipe 1",
    "territorio": "Nome do território"
  },
  "geometry": { "type": "Point", "coordinates": [-51.0939, -29.9509] }
}
```

Atenção à ordem **[longitude, latitude]**. Sem coordenada real da unidade, não crie a feição: é preferível a unidade não aparecer no mapa a aparecer no lugar errado.

## 7. Como executar localmente

O navegador bloqueia `fetch` de arquivos abertos por `file://`, então use um servidor local:

```bash
python -m http.server 8000
```

Depois abra `http://localhost:8000/`. A página `consulta/index.html` é autocontida e abre com duplo clique, sem servidor.

Para regerar os dados (só é preciso quando as fontes mudam):

```bash
cd dados && python ../scripts/fetch_osm.py && python ../scripts/cnefe.py && python ../scripts/parse.py && python ../scripts/lines_osm.py && python ../scripts/build.py && python ../scripts/final.py
```

e, da raiz:

```bash
python scripts/geojson.py && python scripts/build_html.py
```

`scripts/geojson.py` gera os arquivos de `data/`; `scripts/build_html.py` gera `consulta/index.html`.

## 8. Como publicar no GitHub Pages

1. **Settings → Pages**.
2. **Source:** *Deploy from a branch*.
3. **Branch:** `main`, pasta `/ (root)`. Salvar.
4. Em um a dois minutos o site fica em `https://ueldomiguel.github.io/cachoeirinha-esf-ubs/`.

O arquivo `.nojekyll` na raiz desliga o processamento Jekyll, que não é necessário aqui.

## 9. Dados territoriais oficiais

Os polígonos e as listas de ruas atualmente publicados vêm de mapa colaborativo público e são **dados de trabalho**. Os limites oficiais das áreas de abrangência, a lotação das equipes e o cadastro das unidades devem ser fornecidos pela **Secretaria Municipal de Saúde de Cachoeirinha**. Quando forem disponibilizados, substitua os arquivos de `data/` conforme a seção 4 — a aplicação passa a exibi-los sem nenhuma alteração de código.

Fontes usadas hoje:

- Áreas, unidades e listas de ruas: mapa colaborativo "Mapeamento unidades de saúde — Cachoeirinha" (Google My Maps).
- Malha viária e limite municipal: OpenStreetMap, contribuidores (ODbL).
- Numeração de endereços e faces de quadra (página de consulta): CNEFE 2022, IBGE, município 4303103.

## 10. Licença

Código sob **MIT** (veja [LICENSE](LICENSE)). Os dados seguem as licenças das respectivas fontes, descritas no mesmo arquivo.
