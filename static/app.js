/* =========================================================
   FISHER - INTERAÇÕES
   Sem bibliotecas externas. Tudo é opcional: se o JavaScript
   falhar, as páginas continuam funcionando.
   ========================================================= */

(function () {
    'use strict';

    var $ = function (seletor, raiz) { return (raiz || document).querySelector(seletor); };
    var $$ = function (seletor, raiz) { return Array.prototype.slice.call((raiz || document).querySelectorAll(seletor)); };

    var reduzirMovimento = window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Função para obter o Token CSRF da Meta Tag ou Input
    function getCsrfToken() {
        var meta = $('meta[name="csrf-token"]');
        if (meta) return meta.content;
        var input = $('input[name="csrf_token"]');
        return input ? input.value : '';
    }

    function formatar(valor, casas) {
        return Number(valor).toLocaleString('pt-BR', {
            minimumFractionDigits: casas,
            maximumFractionDigits: casas
        });
    }

    function paraNumero(texto) {
        var n = parseFloat(String(texto).replace(',', '.'));
        return isNaN(n) ? null : n;
    }


    /* -----------------------------------------------------
       MENSAGENS: somem sozinhas
       ----------------------------------------------------- */

    function fecharToast(toast) {
        toast.classList.add('saindo');
        setTimeout(function () { toast.remove(); }, 300);
    }

    function iniciarToasts() {
        $$('.toast').forEach(function (toast, i) {
            setTimeout(function () { fecharToast(toast); }, 6000 + i * 800);
        });

        document.addEventListener('click', function (e) {
            var botao = e.target.closest('[data-fechar-toast]');
            if (botao) fecharToast(botao.closest('.toast'));
        });
    }


    /* -----------------------------------------------------
       MEDIDOR: número que sobe junto com a água
       ----------------------------------------------------- */

    function iniciarContagem() {
        $$('[data-contar]').forEach(function (el) {
            var alvo = parseInt(el.getAttribute('data-contar'), 10);
            if (isNaN(alvo) || reduzirMovimento) return;

            var inicio = null;
            var duracao = 1600;

            el.textContent = '0';

            function passo(t) {
                if (inicio === null) inicio = t;
                var p = Math.min(1, (t - inicio) / duracao);
                var suave = 1 - Math.pow(1 - p, 3);
                el.textContent = Math.round(alvo * suave);
                if (p < 1) requestAnimationFrame(passo);
            }

            requestAnimationFrame(passo);
        });
    }


    /* -----------------------------------------------------
       JANELAS: registrar ração e confirmar exclusão
       ----------------------------------------------------- */

    function abrirDialogo(dlg) {
        if (typeof dlg.showModal === 'function') dlg.showModal();
        else dlg.setAttribute('open', '');
    }

    function iniciarJanelas() {
        var dlgTrato = $('#dlg-trato');
        var dlgExcluir = $('#dlg-excluir');

        // Configura a submissão via FETCH DELETE para a janela de exclusão
        var formExcluir = $('#form-excluir');
        if (formExcluir && !formExcluir.dataset.bound) {
            formExcluir.dataset.bound = 'true';
            formExcluir.addEventListener('submit', function (evt) {
                evt.preventDefault();
                
                fetch(formExcluir.action, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/json'
                    }
                })
                .then(function (r) {
                    if (r.ok) {
                        window.location.reload();
                    } else {
                        alert('Erro ao excluir o item.');
                    }
                })
                .catch(function () {
                    alert('Erro de conexão com o servidor.');
                });
            });
        }

        document.addEventListener('click', function (e) {

            var fechar = e.target.closest('[data-fechar]');
            if (fechar) {
                var dlg = fechar.closest('dialog');
                if (dlg) dlg.close();
                return;
            }

            // Clique no fundo escuro fecha a janela
            if (e.target.tagName === 'DIALOG') {
                e.target.close();
                return;
            }

            var trato = e.target.closest('[data-trato]');
            if (trato && dlgTrato) {
                prepararTrato(dlgTrato, trato);
                return;
            }

            var excluir = e.target.closest('[data-excluir]');
            if (excluir && dlgExcluir) {
                if (formExcluir) {
                    formExcluir.action = excluir.getAttribute('data-acao');
                }
                $('#excluir-titulo').textContent = excluir.getAttribute('data-titulo') || 'Excluir?';
                $('#excluir-texto').textContent = excluir.getAttribute('data-texto') || '';
                $('#excluir-botao').textContent = excluir.getAttribute('data-botao') || 'Excluir';
                abrirDialogo(dlgExcluir);
            }
        });
    }

    function prepararTrato(dlg, botao) {
        var meta = paraNumero(botao.getAttribute('data-meta')) || 0;
        var falta = paraNumero(botao.getAttribute('data-falta')) || 0;
        var refeicao = paraNumero(botao.getAttribute('data-refeicao')) || 0;

        var formTrato = $('#form-trato');
        if (formTrato) {
            formTrato.action = botao.getAttribute('data-acao');
            
            // Injeta o Token CSRF se não existir
            if (!formTrato.querySelector('input[name="csrf_token"]')) {
                var inputCsrf = document.createElement('input');
                inputCsrf.type = 'hidden';
                inputCsrf.name = 'csrf_token';
                inputCsrf.value = getCsrfToken();
                formTrato.appendChild(inputCsrf);
            }
        }

        $('#trato-tanque').textContent = 'Tanque: ' + botao.getAttribute('data-nome');

        $('#trato-resumo').innerHTML =
            'Meta de hoje: <b>' + formatar(meta, 2) + ' kg</b>. ' +
            (falta > 0
                ? 'Ainda faltam <b>' + formatar(falta, 2) + ' kg</b>.'
                : 'A meta de hoje já foi cumprida.');

        var campo = $('#trato-qtd');
        campo.value = refeicao > 0 ? formatar(Math.min(refeicao, falta || refeicao), 2) : '';

        var atalhos = $('#trato-atalhos');
        atalhos.innerHTML = '';

        function atalho(texto, valor) {
            if (!(valor > 0)) return;
            var b = document.createElement('button');
            b.type = 'button';
            b.textContent = texto;
            b.addEventListener('click', function () {
                campo.value = formatar(valor, 2);
                campo.focus();
            });
            atalhos.appendChild(b);
        }

        atalho('1 refeição (' + formatar(refeicao, 2) + ' kg)', refeicao);
        atalho('O que falta (' + formatar(falta, 2) + ' kg)', falta);

        abrirDialogo(dlg);
        setTimeout(function () { campo.focus(); campo.select(); }, 60);
    }


    /* -----------------------------------------------------
       LISTA DE TANQUES: busca, filtros e ordenação
       ----------------------------------------------------- */

    function iniciarTabela() {
        var tabela = $('#tabela-tanques');
        if (!tabela) return;

        var corpo = tabela.tBodies[0];
        var linhas = $$('tr[data-nome]', corpo);
        var busca = $('#filtro-busca');
        var especie = $('#filtro-especie');
        var nivel = $('#filtro-nivel');
        var contagem = $('#filtro-contagem');
        var semResultado = $('#linha-sem-resultado');

        function normalizar(t) {
            return (t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        }

        function filtrar() {
            var termo = normalizar(busca ? busca.value.trim() : '');
            var visiveis = 0;

            linhas.forEach(function (tr) {
                var texto = normalizar(tr.dataset.nome + ' ' + tr.dataset.especie);
                var ok =
                    (!termo || texto.indexOf(termo) !== -1) &&
                    (!especie || !especie.value || tr.dataset.especie === especie.value) &&
                    (!nivel || !nivel.value || tr.dataset.nivel === nivel.value);

                tr.hidden = !ok;
                if (ok) visiveis++;
            });

            if (semResultado) semResultado.hidden = visiveis !== 0;
            if (contagem) contagem.textContent = 'Mostrando ' + visiveis + ' de ' + linhas.length;
        }

        [busca, especie, nivel].forEach(function (el) {
            if (el) {
                el.addEventListener('input', filtrar);
                el.addEventListener('change', filtrar);
            }
        });

        // Ordenar clicando no título da coluna

        $$('th[data-ordenar]', tabela).forEach(function (th) {
            th.tabIndex = 0;

            function ordenar() {
                var tipo = th.getAttribute('data-ordenar');
                var crescente = th.getAttribute('aria-sort') !== 'ascending';

                $$('th', tabela).forEach(function (o) { o.removeAttribute('aria-sort'); });
                th.setAttribute('aria-sort', crescente ? 'ascending' : 'descending');

                var posicao = Array.prototype.indexOf.call(th.parentNode.children, th);

                linhas.sort(function (a, b) {
                    var va = a.children[posicao].getAttribute('data-valor');
                    var vb = b.children[posicao].getAttribute('data-valor');

                    if (tipo === 'numero') {
                        va = parseFloat(va); vb = parseFloat(vb);
                        return crescente ? va - vb : vb - va;
                    }
                    return crescente ? va.localeCompare(vb, 'pt-BR') : vb.localeCompare(va, 'pt-BR');
                });

                linhas.forEach(function (tr) { corpo.insertBefore(tr, semResultado); });
            }

            th.addEventListener('click', ordenar);
            th.addEventListener('keydown', function (e) {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ordenar(); }
            });
        });

        filtrar();
    }


    /* -----------------------------------------------------
       FORMULÁRIO DE TANQUE: referência da espécie ao vivo
       ----------------------------------------------------- */

    function iniciarFormularioTanque() {
        var dadosEl = $('#perfis-json');
        var campoEspecie = $('#especie');
        if (!dadosEl || !campoEspecie) return;

        var perfis = JSON.parse(dadosEl.textContent);
        var campoQtd = $('#quantidade');
        var campoVol = $('#volume_m3');

        function normalizar(t) {
            return (t || '').toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
        }

        function achar(nome) {
            var n = normalizar(nome);
            if (!n) return null;
            for (var chave in perfis) {
                if (chave === 'padrao') continue;
                var palavras = perfis[chave].palavras;
                for (var i = 0; i < palavras.length; i++) {
                    if (n.indexOf(palavras[i]) !== -1) return perfis[chave];
                }
            }
            return perfis.padrao;
        }

        function atualizar() {
            var p = achar(campoEspecie.value);

            if (!p) {
                $('#perfil-nome').textContent = 'Referência da espécie';
                $('#perfil-sub').textContent =
                    'Digite a espécie para ver a faixa de temperatura e a taxa de ração usadas no cálculo.';
                ['temp', 'taxa', 'prot'].forEach(function (id) { $('#perfil-' + id).textContent = '-'; });
            } else {
                var generico = p === perfis.padrao;

                $('#perfil-nome').textContent = generico ? 'Espécie personalizada' : p.nome;
                $('#perfil-sub').textContent = generico
                    ? 'Não temos uma tabela específica. Usamos valores gerais para peixes de água doce.'
                    : 'Valores usados no cálculo da ração deste tanque.';
                $('#perfil-temp').textContent = p.temp_ideal[0] + ' a ' + p.temp_ideal[1] + ' °C';
                $('#perfil-taxa').textContent =
                    formatar(p.taxa_min, 1) + '% a ' + formatar(p.taxa_max, 1) + '% (conforme o peso)';
                $('#perfil-prot').textContent = p.proteina_min + '% a ' + p.proteina_max + '% PB';
            }

            var qtd = campoQtd ? paraNumero(campoQtd.value) : null;
            var vol = campoVol ? paraNumero(campoVol.value) : null;
            var densEl = $('#perfil-dens');
            if (densEl) {
                densEl.textContent = (qtd > 0 && vol > 0)
                    ? formatar(qtd / vol, 1) + ' peixes por m³'
                    : 'Informe o volume para calcular';
            }
        }

        [campoEspecie, campoQtd, campoVol].forEach(function (el) {
            if (el) el.addEventListener('input', atualizar);
        });

        atualizar();
    }


    /* -----------------------------------------------------
       BIOMETRIA: simulador de ração enquanto digita
       ----------------------------------------------------- */

    function iniciarSimulador() {
        var form = $('#form-biometria');
        if (!form) return;

        var url = form.getAttribute('data-simular');
        var peso = $('#peso_medio');
        var temp = $('#temperatura');
        var saida = $('#simulador');
        var espera = null;
        var pedido = 0;

        function simular() {
            var p = paraNumero(peso.value);
            var t = paraNumero(temp.value);

            if (!(p > 0) || t === null) {
                saida.innerHTML = '<small>Preencha o peso e a temperatura para simular a ração.</small>';
                return;
            }

            var meu = ++pedido;

            fetch(url + '?peso=' + encodeURIComponent(p) + '&temp=' + encodeURIComponent(t), {
                headers: { 'Accept': 'application/json' }
            })
                .then(function (r) { return r.json(); })
                .then(function (c) {
                    if (meu !== pedido || c.erro) return;

                    saida.innerHTML =
                        'Com esses valores a ração seria <b>' + formatar(c.total_kg, 2) + ' kg por dia</b>' +
                        (c.refeicoes ? ' (' + c.refeicoes + 'x de ' + formatar(c.por_refeicao_kg, 2) + ' kg)' : '') +
                        '.<small>' + formatar(c.taxa_ajustada, 2) + '% do peso vivo. ' +
                        c.temp_mensagem + '</small>';
                })
                .catch(function () {
                    saida.innerHTML = '<small>Não foi possível simular agora. Você ainda pode salvar a biometria.</small>';
                });
        }

        function agendar() {
            clearTimeout(espera);
            espera = setTimeout(simular, 250);
        }

        if (peso && temp) {
            peso.addEventListener('input', agendar);
            temp.addEventListener('input', agendar);
            simular();
        }
    }


    /* -----------------------------------------------------
       GRÁFICOS DE LINHA (SVG puro)
       ----------------------------------------------------- */

    function desenharLinha(svg, pontos, opcoes) {
        var NS = 'http://www.w3.org/2000/svg';
        var L = Math.max(280, Math.round(svg.getBoundingClientRect().width)) || 720;
        var A = 190;
        var margem = { e: 44, d: 14, t: 14, b: 26 };

        svg.setAttribute('viewBox', '0 0 ' + L + ' ' + A);
        svg.innerHTML = '';

        var valores = pontos.map(function (p) { return p.y; });
        var minimo = Math.min.apply(null, valores);
        var maximo = Math.max.apply(null, valores);

        if (opcoes.faixa) {
            minimo = Math.min(minimo, opcoes.faixa[0]);
            maximo = Math.max(maximo, opcoes.faixa[1]);
        }

        var folga = (maximo - minimo) * 0.15 || 1;
        minimo = Math.max(0, minimo - folga);
        maximo = maximo + folga;

        function x(i) {
            return margem.e + (pontos.length === 1 ? 0 : i * (L - margem.e - margem.d) / (pontos.length - 1));
        }
        function y(v) {
            return margem.t + (maximo - v) * (A - margem.t - margem.b) / (maximo - minimo);
        }
        function criar(tag, atributos, texto) {
            var el = document.createElementNS(NS, tag);
            for (var k in atributos) el.setAttribute(k, atributos[k]);
            if (texto !== undefined) el.textContent = texto;
            svg.appendChild(el);
            return el;
        }

        // Linhas de grade e valores do eixo
        for (var g = 0; g <= 3; g++) {
            var v = minimo + (maximo - minimo) * g / 3;
            criar('line', { x1: margem.e, x2: L - margem.d, y1: y(v), y2: y(v), 'class': 'grade' });
            criar('text', { x: margem.e - 8, y: y(v) + 4, 'text-anchor': 'end', 'class': 'eixo' }, formatar(v, opcoes.casas));
        }

        // Faixa ideal (temperatura)
        if (opcoes.faixa) {
            criar('rect', {
                x: margem.e, width: L - margem.e - margem.d,
                y: y(opcoes.faixa[1]), height: y(opcoes.faixa[0]) - y(opcoes.faixa[1]),
                'class': 'faixa-ideal'
            });
        }

        var caminho = pontos.map(function (p, i) { return (i ? 'L' : 'M') + x(i) + ' ' + y(p.y); }).join(' ');

        if (!opcoes.faixa) {
            criar('path', {
                d: caminho + ' L' + x(pontos.length - 1) + ' ' + (A - margem.b) + ' L' + x(0) + ' ' + (A - margem.b) + ' Z',
                'class': 'area'
            });
        }

        criar('path', { d: caminho, 'class': 'linha' + (opcoes.classe ? ' ' + opcoes.classe : '') });

        var passo = Math.ceil(pontos.length / 8);

        pontos.forEach(function (p, i) {
            var c = criar('circle', {
                cx: x(i), cy: y(p.y), r: 4,
                'class': 'ponto' + (opcoes.classePonto ? ' ' + opcoes.classePonto : '')
            });
            var dica = document.createElementNS(NS, 'title');
            dica.textContent = p.rotulo + ': ' + formatar(p.y, opcoes.casas) + ' ' + opcoes.unidade;
            c.appendChild(dica);

            if (i % passo === 0 || i === pontos.length - 1) {
                criar('text', { x: x(i), y: A - 6, 'text-anchor': 'middle', 'class': 'eixo' }, p.rotulo);
            }
        });
    }

    function iniciarGraficos() {
        var dadosEl = $('#serie-json');
        if (!dadosEl) return;

        var dados = JSON.parse(dadosEl.textContent);

        var peso = $('#grafico-peso');
        var temp = $('#grafico-temp');

        function desenhar() {
            if (peso) {
                desenharLinha(peso, dados.serie.map(function (s) { return { rotulo: s.data, y: s.peso }; }),
                    { casas: 0, unidade: 'g' });
            }

            if (temp) {
                desenharLinha(temp, dados.serie.map(function (s) { return { rotulo: s.data, y: s.temp }; }),
                    { casas: 1, unidade: '°C', faixa: dados.ideal, classe: 'linha-temp', classePonto: 'ponto-temp' });
            }
        }

        desenhar();

        // Redesenha se a janela mudar de tamanho
        var espera = null;
        window.addEventListener('resize', function () {
            clearTimeout(espera);
            espera = setTimeout(desenhar, 150);
        });
    }


    /* -----------------------------------------------------
       INÍCIO
       ----------------------------------------------------- */

    document.addEventListener('DOMContentLoaded', function () {
        iniciarToasts();
        iniciarContagem();
        iniciarJanelas();
        iniciarTabela();
        iniciarFormularioTanque();
        iniciarSimulador();
        iniciarGraficos();
    });

})();