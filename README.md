# Mercado BR

Painel Streamlit para acompanhamento de indicadores financeiros, ações brasileiras, gráficos e notícias.

## Executar localmente

```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```



## Notas

- A pasta `assets` contém a imagem de capa criada para o projeto.
- As cotações e notícias dependem de provedores externos e podem falhar, atrasar ou limitar requisições.
- A imagem de capa é ilustrativa. Miniaturas de notícias são buscadas no RSS e nos metadados dos sites originais; não é possível garantir uma imagem para todas as matérias.
- Este painel é informativo e não constitui recomendação de investimento.
