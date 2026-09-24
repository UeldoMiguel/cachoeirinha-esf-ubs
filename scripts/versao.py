# -*- coding: utf-8 -*-
"""Carimba a versão nos links de CSS e JS do index.html.

Sem isso, o navegador (e o CDN do GitHub Pages) continua servindo o arquivo
antigo depois de uma publicação. O carimbo é a data e hora da geração.

Rode da raiz do projeto: python scripts/versao.py
"""
import datetime
import io
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVOS = ('css/style.css', 'js/tema.js', 'js/map.js', 'js/consulta.js')


def main():
    versao = datetime.datetime.now().strftime('%Y%m%d-%H%M')
    caminho = os.path.join(RAIZ, 'index.html')
    html = io.open(caminho, encoding='utf-8').read()
    for arq in ARQUIVOS:
        html = re.sub(r'"' + re.escape(arq) + r'(\?v=[^"]*)?"',
                      '"' + arq + '?v=' + versao + '"', html)
    io.open(caminho, 'w', encoding='utf-8').write(html)
    print('versão dos assets:', versao)


if __name__ == '__main__':
    main()
