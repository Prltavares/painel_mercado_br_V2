# Mercado BR

Painel Streamlit para acompanhamento de indicadores financeiros, ações brasileiras, gráficos e notícias.

## Executar localmente

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

## Publicar na internet

### Streamlit Community Cloud (recomendado)

1. Crie um repositório no GitHub e envie `app.py`, `requirements.txt`, a pasta `.streamlit` e a pasta `assets`.
2. Acesse <https://share.streamlit.io/> e conecte sua conta GitHub.
3. Escolha o repositório, a branch `main` e o arquivo `app.py`.
4. Clique em Deploy. O serviço disponibilizará um endereço `*.streamlit.app`.

### Render (alternativa)

Envie o projeto para o GitHub, abra <https://render.com/>, crie um novo Web Service a partir do repositório e deixe o Render usar o arquivo `render.yaml`. A instância gratuita pode entrar em suspensão quando fica inativa.

## Notas

- A pasta `assets` contém a imagem de capa criada para o projeto.
- As cotações e notícias dependem de provedores externos e podem falhar, atrasar ou limitar requisições.
- A imagem de capa é ilustrativa. Miniaturas de notícias são buscadas no RSS e nos metadados dos sites originais; não é possível garantir uma imagem para todas as matérias.
- Este painel é informativo e não constitui recomendação de investimento.
