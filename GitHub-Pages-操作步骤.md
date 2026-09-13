# GitHub Pages 操作步骤（照着做就行）

> 目标：把「每日简报」发布成公网网站，并且每天自动更新，不用你管。
> 全程只需要你登录一次 GitHub，之后不再需要任何操作。首次耗时约 5 分钟。

---

## 第 1 步 · 在 GitHub 建一个空仓库（约 1 分钟）

1. 打开 https://github.com ，没有账号先点 **Sign up** 注册（邮箱 + 密码 + 用户名，一般不会卡验证码）。
2. 登录后点右上角 **+** → **New repository**。
3. 填写：

| 项目 | 填什么 |
| --- | --- |
| Repository name | `daily-brief`（英文小写，会出现在网址里，可自取） |
| Description | 可留空 |
| 公开性 | 选 **Public**（免费版 Pages 需要公开仓库） |

4. 下面三个勾选项**一个都不要勾**（Add a README / .gitignore / license）——仓库必须是空的，否则推送会冲突。
5. 点 **Create repository**。
6. 页面会显示仓库地址，复制下来，形如 `https://github.com/你的用户名/daily-brief.git`。

---

## 第 2 步 · 一键推送（约 1 分钟）

双击 **`推送到GitHub.cmd`**：

1. 它会先抓一次最新新闻；
2. 提示「请粘贴你刚建的 GitHub 仓库地址」时，把第 1 步复制的地址粘进去，回车；
3. 第一次推送会弹出浏览器窗口让你登录 GitHub，点同意/授权即可（以后不再问）；
4. 看到「推送完成！」就成了。

如果你更喜欢手动敲命令，等价操作是：

```powershell
cd "C:\Users\Lenovo\Documents\Codex\2026-09-08\tracking-news\outputs\新闻日报"
git init -b main
git add -A
git commit -m "init: 每日简报"
git remote add origin https://github.com/你的用户名/daily-brief.git
git push -u origin main
```

---

## 第 3 步 · 打开 Pages（只需做一次，约 1 分钟）

1. 进入你刚推上去的仓库页面；
2. 点仓库顶部 **Settings** → 左侧栏找 **Pages**；
3. **Source** 选 **GitHub Actions**（注意：不要选 “Deploy from a branch”）；
4. 到仓库顶部 **Actions** 标签，左侧选「每日更新简报」，点右侧 **Run workflow** 手动跑一次；
5. 等 1 分钟左右（绿勾=成功），网址会显示在 Pages 页面顶部，形如：

```
https://你的用户名.github.io/daily-brief/
```

打开它就是完整站点。之后每天北京时间 06:30 云端会自动更新，你什么都不用做。

---

## 之后会变成什么样

```
每天 06:30（北京时间）
  → GitHub 服务器抓取新闻、生成页面
  → 自动提交当天快照
  → 自动发布到 https://你的用户名.github.io/daily-brief/
```

每次更新都会在仓库里留一条提交记录，历史可回溯；`data/archive/` 里存着每一期的数据。

---

## 常见问题

### 推送失败说没登录？

重新双击 `推送到GitHub.cmd`，按弹出的浏览器窗口完成 GitHub 授权即可。

### 推送失败说 rejected / 冲突？

建仓库时勾了 README 之类的初始文件。最简单的做法：把那个仓库删掉，重建一个**空仓库**，再推一次。

### 网址打开是 404？

两件事检查：① Actions 里那次运行是否成功（绿勾）；② Settings → Pages 的 Source 是否已选成 **GitHub Actions**。首次发布有时要等 1–3 分钟。

### 想要更短的网址？

把仓库名取成 `你的用户名.github.io`，网址就变成 `https://你的用户名.github.io/`。

### 想用自己的域名？

仓库 Settings → Pages → Custom domain，填你的域名，然后到域名商加一条 CNAME 记录指向 `你的用户名.github.io`。

### 不想用命令行，能用网页传吗？

可以。在空仓库页面点 **uploading an existing file**，把 `新闻日报` 文件夹**里面的内容**（不是文件夹本身）拖进去。注意两点：

1. `.github` 是隐藏文件夹，先在资源管理器「查看 → 显示 → 隐藏的项目」打开它，再 Ctrl+A 全选，否则自动更新的配置文件会漏掉；
2. 网页上传无法保留空文件夹，我们这里没有空文件夹，不影响。

---

## 顺带一提

GitHub 的服务器能正常访问 HTTPS，所以部署上去以后，我可以把新闻源换成覆盖面更广的一批（人民网、新华网、澎湃、36氪等），
内容质量会比现在这个「只能走 HTTP」的版本更好。要换就跟我说一声。
