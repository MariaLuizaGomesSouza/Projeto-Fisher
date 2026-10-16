# Projeto-Fisher

O Sistema de Controle de Custo Alimentar e Biometria de Peixes foi desenvolvido para auxiliar piscicultores no gerenciamento da alimentação dos peixes, reduzindo desperdícios e melhorando o controle da produção.

O sistema permite registrar as biometrias (pesagens amostrais dos peixes), calcular a biomassa total de cada tanque e estimar a quantidade ideal de ração que deve ser fornecida diariamente.

## Recursos

- **Painel central** com o bem-estar geral (%), nível de ração (%), adequação da temperatura (%), alertas e as últimas alterações feitas.
- **Cálculo de ração** por espécie, faixa de peso e temperatura, com a taxa em % do peso vivo, refeições por dia e proteína recomendada (arquivo `racao.py`).
- **Bem-estar de cada tanque** (0 a 100%): temperatura, alimentação e biometria em dia.
- **Estoque de ração** com desconto automático a cada trato e previsão de dias restantes.
- **Tanques**: cadastrar, editar, duplicar, excluir, buscar, filtrar, ordenar e exportar para planilha (CSV).
- **Biometria** com simulador ao vivo, gráficos de crescimento e temperatura, registro de tratos e de mortalidade.
- **Histórico** completo de tudo que foi alterado.

## Como rodar

```
pip install -r requirements.txt
python app.py
```

O banco existente (`instance/fisher.db`) é atualizado sozinho na primeira execução, sem perder dados.

## Ajustando o cálculo

As faixas de temperatura e as taxas de ração de cada espécie ficam na tabela `PERFIS`, no início do arquivo `racao.py`. São referências gerais de manejo: confirme com o seu zootecnista ou técnico antes de adotar.
