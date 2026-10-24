# Jedi LSFG-VK

Plugin para o [Decky Loader](https://github.com/SteamDeckHomebrew/decky-loader) que traz a geração de frames do Lossless Scaling para o Steam Deck com **um único controle: o FPS alvo**.

Você escolhe quantos FPS quer ver na tela. O plugin cuida do resto.

> Plugin comunitário e não oficial. Não tem ligação com os desenvolvedores do Lossless Scaling, do lsfg-vk ou do MAKO.

*English summary at the end.*

## O que ele faz

Em vez de escolher um multiplicador fixo (2x, 3x, 4x), você define o **FPS alvo** de cada jogo. A partir disso, o plugin:

1. **Nunca limita os FPS reais.** O alvo é o mínimo que você quer ver, não um teto. Se o jogo roda a 65 FPS com alvo de 60, você vê os 65 FPS reais, sem frames gerados.
2. **Gera só os frames que faltam.** Se o jogo cai para 50 FPS, a geração completa os 10 que faltam (cerca de 1,2x). A 30 FPS fica em 2x, a 20 FPS vai a 3x.
3. **Sobe e desce aos poucos.** O multiplicador muda em degraus pequenos (2,1x, 2,2x, 2,3x…) em vez de pular de 2x para 3x, o que deixa a transição suave.
4. **Volta para os frames reais quando o jogo melhora.** A cada 3 segundos o plugin confere se o jogo já consegue rodar mais rápido sozinho. Se consegue, a geração diminui ou para.
5. **Para em 4x.** Acima disso a latência e os artefatos ficam ruins, então a geração nunca passa de 4x.

Essas regras são automáticas e não aparecem na tela. A única coisa que você ajusta é o FPS alvo, e a mudança vale na hora, com o jogo rodando.

O alvo vai de 60 a 120 FPS. Use um valor igual ou menor que a taxa de atualização da tela (60 Hz no Steam Deck LCD, até 90 Hz no OLED): frames acima disso não aparecem e só sobrecarregam a fila de apresentação. Perfis salvos com alvo abaixo de 60 por versões anteriores passam para 60 quando o plugin carrega.

## Leve durante o jogo

Com o menu do Decky fechado, o plugin não faz nenhum trabalho em segundo plano: não consulta o backend, não lê arquivos e não abre processos. A verificação de jogos e apps Flatpak em execução só acontece com o menu aberto, e lê as configurações do Flatpak direto do disco, sem chamar o comando `flatpak` para cada app.

## Qual versão do Lossless Scaling usar

Qualquer uma que traga a `Lossless.dll`: a branch padrão da Steam e a branch `lsfg-vk` (a versão para Linux) funcionam. O plugin acha a DLL sozinho e só pede para trocar de branch se ela não for encontrada.

O que gera os frames é o [MAKO Renderer](https://github.com/eugeniosegala/MAKO) 4.6.0, numa release estável instalada pelo plugin e conferida por checksum. Ele é que permite o FPS alvo: a camada do lsfg-vk 2.0 só trabalha com multiplicadores inteiros e não tem modo adaptativo.

## Instalação

1. Baixe o arquivo **Jedi LSFG-VK.zip** na página de [Releases](https://github.com/sauliiin/Jedi-LSFG-VK/releases).
2. No Game Mode, abra as configurações do Decky, ative o **Developer Mode** e use **Developer → Install Plugin from Zip**.
3. Instale o [Lossless Scaling](https://store.steampowered.com/app/993090/Lossless_Scaling/) pela Steam. Funciona na branch padrão e na branch `lsfg-vk`.
4. Abra o plugin e toque em **Install MAKO Renderer**.

### Atualizações

O plugin confere os releases do GitHub quando carrega. Se houver uma versão nova, aparece um aviso: toque nele, ou em **Settings → Plugin update → Update**, e confirme no Decky. O Decky baixa a versão nova, confere o checksum e recarrega o plugin. A conferência é feita uma vez ao carregar e ao abrir a aba Settings, nunca durante o jogo.

## Como usar

1. Na aba **Steam** ou **Non-Steam**, escolha um jogo.
2. Toque em **Enable for next launch**. O plugin adiciona `~/.jedi-lsfg %command%` às opções de inicialização do jogo.
3. Ajuste o **Target FPS** (60 a 120).

Apps Flatpak são ativados na aba **Flatpak**. Na primeira vez, o plugin baixa a extensão Flatpak do renderizador (cerca de 120 MB).

### Outras opções por jogo

- **Flow Scale**: valores menores deixam a estimativa de movimento mais leve.
- **Performance Mode**: modelo de geração mais leve. Já vem ligado.
- **Preserve Swapchain Image Count**: só para jogos que não abrem.
- **Workarounds**: desativar o Steam Deck Mode do jogo e forçar o Zink em jogos OpenGL.

## Convivência com outros plugins

- As configurações ficam em `~/.config/jedi-lsfg-vk/` e não mexem nos perfis do decky-lsfg-vk nem do MAKO Decky.
- Ao ativar um jogo, o plugin substitui um `~/.lsfg` ou `mako-run` que esteja nas opções de inicialização, porque duas camadas de geração de frames no mesmo jogo não funcionam juntas.
- Se o MAKO Renderer já estava instalado antes, desinstalar este plugin não o remove.

## Créditos

- [decky-lsfg-vk](https://github.com/xXJSONDeruloXx/decky-lsfg-vk), de Kurt Himebauch, plugin em que este projeto se baseia.
- [MAKO](https://github.com/eugeniosegala/MAKO), de Eugenio Segala e colaboradores (GPL-3.0-or-later), que fornece o renderizador e a geração de frames adaptativa. O MAKO Renderer é baixado da release oficial, sem modificações.
- [lsfg-vk](https://lsfg-vk.dev/), de PancakeTAS, que trouxe a geração de frames do Lossless Scaling para o Linux.
- Desenvolvedores do [Lossless Scaling](https://store.steampowered.com/app/993090/Lossless_Scaling/).
- Equipe do Decky Loader.

---

## English summary

Jedi LSFG-VK is a Decky Loader plugin with a single control: the **target FPS** (60–120). The target is a floor, not a cap: a game that runs above it is shown at its native FPS, and frame generation only fills the gap below it, in small fractional steps up to 4x. Every 3 seconds MAKO checks whether the game can run faster on its own and reduces generation when it can. These rules are automatic and hidden. It reads Lossless.dll from Lossless Scaling (default or lsfg-vk Steam branch) and uses the pinned stable MAKO Renderer 4.6.0. Install the ZIP from Releases through **Developer → Install Plugin from Zip**, then select **Install MAKO Renderer** in the plugin. From 1.2.0 on, the plugin checks GitHub when it loads and updates itself through Decky's installer after you confirm.
