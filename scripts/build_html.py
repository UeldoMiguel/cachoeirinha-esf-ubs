# -*- coding: utf-8 -*-
"""Injeta dados/final.json no template e gera as duas saídas.

consulta/index.html  documento completo, com <meta charset>: é a página publicada
                     em /consulta/ no GitHub Pages e também abre offline
dist/artifact.html   só o conteúdo, como o Artifact espera (ele monta o <head>)

Rode da raiz do projeto: python scripts/build_html.py
"""
import io, os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def main():
    tpl = io.open(os.path.join(RAIZ, 'scripts', 'page.template.html'), encoding='utf-8').read()
    dados = io.open(os.path.join(RAIZ, 'dados', 'final.json'), encoding='utf-8').read()
    corpo = tpl.replace('__DATA__', dados)

    os.makedirs(os.path.join(RAIZ, 'dist'), exist_ok=True)
    io.open(os.path.join(RAIZ, 'dist', 'artifact.html'), 'w', encoding='utf-8').write(corpo)

    completo = (
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        '<style>:root{color-scheme:light dark}body{margin:0}img{max-width:100%}'
        '[hidden]{display:none!important}</style>\n'
        + corpo.split('<div class="wrap">')[0] +
        '</head>\n<body>\n<div class="wrap">'
        + corpo.split('<div class="wrap">', 1)[1] +
        '\n</body>\n</html>\n'
    )
    os.makedirs(os.path.join(RAIZ, 'consulta'), exist_ok=True)
    io.open(os.path.join(RAIZ, 'consulta', 'index.html'), 'w', encoding='utf-8').write(completo)
    print('dist/artifact.html:', len(corpo), 'bytes')
    print('consulta/index.html:', len(completo), 'bytes')

if __name__ == '__main__':
    main()
