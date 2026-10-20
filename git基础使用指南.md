J J 加速器

git config --global http.proxy http://127.0.0.1:7897
git config --global https.proxy http://127.0.0.1:7897

Nano

git config --global http.proxy http://127.0.0.1:65532
git config --global https.proxy http://127.0.0.1:65532

出现服务器错误，把端口改成vpn端口（设置搜索代理），即可



tree /f /a : 看文件树

git clone https://github.com/用户名/项目名.git : 首次拉取已有的项目

git init : 初始化文件夹，后面就能用git了（clone是第一次拉取已有项目，init是新项目，单词initialize）

git status : 查add但未commit的 

git add .  : 暂存文件，把文件进入待存区，这个`.`表示路径内全部文件

git add .\aaa\bbb\c.md   : 暂存文件，把文件进入待存区，这个`.\xxx`表示相对路径文件

git commit -m "chore: 配置 Git LFS 跟踪大文件"   ❌不规范
git commit -m "chore(data): 通过 LFS 添加大文件数据集"   ✅规范

git commit -m "message" : 提交（不可撤回了喔），并手动写入提交了啥，会记录到上面，方便以后回看

git push : 推送进去，即真正传到github上



git branch : 查看分支名

git push oringin main



git pull：下次拉取再用，一定要记得先拉取最新版本再修改，不然可能别人改过，会有冲突喔