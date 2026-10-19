# 在线展示网站

地址：https://PYxuejiang.github.io/t1d-wearable-lab/

GitHub Pages 托管 React / Three.js 的静态生产构建；首页为交互手表，`#research` 为研究证据页。关闭本地电脑后，访问者仍可使用网站。算法训练与数据采集不在网页服务器执行。

发布源使用 GitHub Actions。`main` 上 `showcase/` 或 Pages 工作流变更会自动构建和发布；也可在 Actions 手动运行 Publish showcase to GitHub Pages。部署失败时保留上一版已发布网站。配置依据：[GitHub 官方自定义 Pages 工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

资源使用相对路径和 Vite `base: './'`，兼容仓库子路径与本地预览。应用使用 hash 导航，无服务端路由。

仅在干净的 GitHub checkout 中构建发布，不上传本地 dist。公开 demo 仅允许已公开的 project_data.json 和 improvement_data.json 两份汇总；工作流在发布前核查此边界。个体回放、真实波形及原始患者数据留在本地忽略目录，不随 Pages 发布。在线版无法加载本地个体回放。
