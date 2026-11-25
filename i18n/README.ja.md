<a id="awesome-hyperframes"></a>

<h1 align="center"><img src="../assets/readme-banner.svg" alt="Awesome HyperFrames" width="1200"></h1>

<p align="center"><strong>HyperFrames で制作する人のための、厳選リソース集。</strong></p>

HyperFrames フレームワークと HyperFrames Studio の動画作品、再利用できるプロジェクト、テンプレート、ツール、学習資料を探せます。

[English](../README.md) · [简体中文](../i18n/README.zh-CN.md) · **日本語** · [Español](../i18n/README.es.md) · [Français](../i18n/README.fr.md) · [Deutsch](../i18n/README.de.md) · [Português (Brasil)](../i18n/README.pt-BR.md) · [한국어](../i18n/README.ko.md)

[Xiaoyingjiang Studio](https://github.com/xiaoyingjiang-studio) が管理する独立したコミュニティのリソース集です。HeyGen の公式プロジェクトではありません。

> このカタログは翻訳されています。リンク先の動画、制作記録、一部のガイドは中国語です。

[はじめに](#start-here) · [注目の制作例](#featured-examples) · [公式リソース](#official-resources) · [学習資料](#learning) · [日次自動カタログ](#automated-catalog) · [テンプレートとツール](#templates-and-tools) · [自動収集](#discovery-and-review) · [貢献する](#contributing)

<a id="start-here"></a>

## はじめに

| 目的 | 入口 |
| --- | --- |
| Studio で制作する | [初めての動画：公式ガイド](https://hyperframes.heygen.com/studio-app/first-video)<br>デスクトップアプリの制作手順を確認できます。 |
| フレームワークで開発する | [公式リポジトリ](https://github.com/heygen-com/hyperframes)<br>ソースコードと公式ドキュメントを確認できます。 |
| 制作例を改変する | [コミュニティの制作例](#featured-examples)<br>完成動画を見て、プロジェクトと制作方法を学べます。 |

<a id="featured-examples"></a>

## 注目の制作例

Xiaoyingjiang Studio による四つのオリジナル制作例です。完成動画、元のプロジェクト、制作記録を掲載しています。動画内の文字は中国語です。

| 製品紹介 | 中国語の解説動画 |
| --- | --- |
| [![製品紹介](https://raw.githubusercontent.com/xiaoyingjiang-studio/hyperframes-cn/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/public/media/product-intro.jpg)](https://xiaoyingjiang.com/showcase/product-intro/) | [![中国語の解説動画](https://raw.githubusercontent.com/xiaoyingjiang-studio/hyperframes-cn/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/public/media/chinese-explainer.jpg)](https://xiaoyingjiang.com/showcase/chinese-explainer/) |
| **製品紹介** — 製品の伝え方、視覚的な階層、場面のタイミング。 | **中国語の解説動画** — 中国語組版、情報の区切り、字幕のタイミング。 |
| [動画と解説（中国語）](https://xiaoyingjiang.com/showcase/product-intro/) · [元のプロジェクト](https://github.com/xiaoyingjiang-studio/hyperframes-cn/tree/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/examples/product-intro) · [制作記録（中国語）](../examples/product-intro/README.md) | [動画と解説（中国語）](https://xiaoyingjiang.com/showcase/chinese-explainer/) · [元のプロジェクト](https://github.com/xiaoyingjiang-studio/hyperframes-cn/tree/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/examples/chinese-explainer) · [制作記録（中国語）](../examples/chinese-explainer/README.md) |

| データの可視化 | 素材の編集 |
| --- | --- |
| [![データの可視化](https://raw.githubusercontent.com/xiaoyingjiang-studio/hyperframes-cn/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/public/media/data-story.jpg)](https://xiaoyingjiang.com/showcase/data-story/) | [![素材の編集](https://raw.githubusercontent.com/xiaoyingjiang-studio/hyperframes-cn/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/public/media/footage-edit.jpg)](https://xiaoyingjiang.com/showcase/footage-edit/) |
| **データの可視化** — サンプルと明記したデータによる動くグラフと比較。 | **素材の編集** — クリップの構成、文字の重ね合わせ、編集のリズム。 |
| [動画と解説（中国語）](https://xiaoyingjiang.com/showcase/data-story/) · [元のプロジェクト](https://github.com/xiaoyingjiang-studio/hyperframes-cn/tree/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/examples/data-story) · [制作記録（中国語）](../examples/data-story/README.md) | [動画と解説（中国語）](https://xiaoyingjiang.com/showcase/footage-edit/) · [元のプロジェクト](https://github.com/xiaoyingjiang-studio/hyperframes-cn/tree/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/examples/footage-edit) · [制作記録（中国語）](../examples/footage-edit/README.md) |


<details>
<summary>検証範囲と再利用条件</summary>

これらは HyperFrames フレームワークの制作例です。製品画面はコンセプト表現で、Studio の操作実測ではありません。[元の検証記録](https://github.com/xiaoyingjiang-studio/hyperframes-cn/blob/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/public/examples/verification.json)には、Windows と HyperFrames 0.9.92 での確認・レンダリングが記載されています。出力は 960 × 540、30 fps、8 秒、音声なしです。このカタログは過去の記録を引用しており、今回の更新では再レンダリングしていません。別の環境やバージョンでは再確認が必要です。元プロジェクトの[コンテンツライセンス](https://github.com/xiaoyingjiang-studio/hyperframes-cn/blob/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/CONTENT_LICENSE.md)と[第三者の権利表記](https://github.com/xiaoyingjiang-studio/hyperframes-cn/blob/2cbf04a35769f80bc6dff8f6332054d63d6cc9e1/THIRD_PARTY_NOTICES.md)をご確認ください。

</details>

<a id="official-resources"></a>

## 公式リソース

- [HyperFrames リポジトリ](https://github.com/heygen-com/hyperframes) — HeyGen が管理する公式フレームワークとソースコード。
- [公式サイトとドキュメント](https://hyperframes.heygen.com/) — 製品情報、制作の入口、公式ドキュメント。
- [Studio のダウンロード](https://hyperframes.studio/studio/download) — 公式アプリと現在のインストール方法。
- [公式ギャラリー](https://hyperframes.heygen.com/examples) — 公式の動画例。ソースの公開範囲と再利用条件は作品ごとに異なります。
- [Studio の最初の動画](https://hyperframes.heygen.com/studio-app/first-video) — デスクトップ制作の公式デモであり、管理者による実行記録ではありません。

<a id="learning"></a>

## 学習資料

公式ドキュメントは上記から参照できます。以下はコミュニティが管理する**中国語**の資料です。

- [HyperFrames 中国語ガイド](https://xiaoyingjiang.com/) — 製品紹介、インストール、入門資料。
- [Studio 入門](https://xiaoyingjiang.com/start/studio/) — デスクトップアプリの中国語ガイド。
- [中国語のフォントと組版](https://xiaoyingjiang.com/guides/chinese-typography/) — フォント選び、文字配置、読みやすい動画設計。
- [ガイドのソース](https://github.com/xiaoyingjiang-studio/hyperframes-cn) — 独立した中国語サイト、制作例、管理記録。

<!-- AUTO-CATALOG:START -->

<a id="automated-catalog"></a>

## 日次自動カタログ

引用元に基づいて自動整理し、AI が紹介文を作成します。プロジェクトの実行や再利用権は独立に確認していません。

[全件を見る (4)](../catalog/README.ja.md)

| リソース | 紹介 |
| --- | --- |
| [Jtensetti/arkivX](<https://github.com/jtensetti/arkivx>)<br><sub>プロジェクト</sub> | スウェーデン語の README が、HyperFrames テンプレートと GSAP・変数を用いてレンダリング動画を生成するショート動画バッチ案件を説明しています。 |
| [jolangker/content-engine](<https://github.com/jolangker/content-engine>)<br><sub>プロジェクト</sub> | コンテンツエンジンのリポジトリで、README は再利用可能なクリエイティブボードでショート動画制作を進め、ブリーフと調査から HyperFrames 工程に至ると述べています。 |
| [johnviklund/j-skills](<https://github.com/johnviklund/j-skills>)<br><sub>ツールと連携</sub> | j-skills の README は、Web ページを MP4 に変換する動画ステップ向けに HyperFrames 自身のスキルを導入し、テレメトリを無効にすることを述べています。 |
| [jogden12/brimm-video-studio](<https://github.com/jogden12/brimm-video-studio>)<br><sub>ツールと連携</sub> | BRIMM Video Studio は brimm-video の次期版とされ、HyperFrames Mac アプリの周辺で動画取り込み、読み取り、プロジェクト生成、書き出し回収を行います。 |

<!-- AUTO-CATALOG:END -->

<a id="templates-and-tools"></a>

## テンプレートとツール

四つの[注目の制作例](#featured-examples)を再利用の出発点にできます。元のプロジェクトの依存関係、再現手順、ライセンスに従ってください。

条件を満たすツールや連携を、原典と確認すべき再利用条件とともに日次カタログへ自動掲載します。上記の手選びの制作例は別に管理します。

<a id="discovery-and-review"></a>

## 自動収集

**毎日の収集 → 重複排除 → 出典と AI の確認 → main へ直接反映。**

毎日の処理が成功すると、条件を満たす項目と八言語の紹介文をカタログとホームに直接反映します。検索だけの一致や証拠が不十分な候補は保留します。週次 Issue や手動マージは不要です。

[日次自動カタログ](../catalog/README.ja.md) · [ワークフローの実行履歴](https://github.com/xiaoyingjiang-studio/awesome-hyperframes/actions/workflows/discover.yml) · [すべての候補記録](https://github.com/xiaoyingjiang-studio/awesome-hyperframes/blob/automation/discovery-state/state.json) · [管理ガイド（中国語）](../discovery/README.md)

<a id="contributing"></a>

## 貢献する

役立つ作品やツールを見つけましたか。[リソースを推薦する](https://github.com/xiaoyingjiang-studio/awesome-hyperframes/issues/new/choose)か、[貢献ガイド（英語）](../CONTRIBUTING.en.md)に沿って PR を提出してください。作者、原典、用途、参考になる点、ソースの有無、ライセンス、実際に確認した内容を記載してください。

手選びの紹介と外部からの PR は管理者が確認します。日次カタログは自動公開します。

<a id="attribution-and-reuse"></a>

## 帰属と再利用

HyperFrames は [HeyGen](https://github.com/heygen-com/hyperframes) が開発しています。リンク先のプロジェクト、動画、商標、フォント、素材の権利は各権利者に帰属し、元のライセンスが適用されます。掲載は複製、再配布、商用利用の許諾を意味しません。本リポジトリは原典へリンクし、第三者のプロジェクト、メディア、インストーラーを転載しません。

---

Xiaoyingjiang Studio · 原典へのリンク · 明確な帰属 · 検証範囲の明示
