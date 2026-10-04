# 服务页素材说明

两张图使用内置 GPT Image 工具生成，应用仍由真实控件处理网络选择、地址输入和服务生命周期。服务页采用大厅的奶白卡片、深绿文字、金色主按钮与圆角输入框；图标通过左右等宽弹性区域居中。装饰背景不能遮挡或替代操作。

当前素材：`weizhuo/static/assets/service-home-background-v2.webp`、`weizhuo/static/assets/service-launch-poster-v2.webp`。v2 使用内置 GPT Image 编辑去除全部麻将，替换为棋盘、木质棋子、骰子与卡牌。公开素材压缩存储；原生 iOS 按显示需要导出 JPEG 和启动 PNG。生成图中的文字只用于宣传页，不承载实时状态。

## 服务背景提示

Use case: stylized-concept. Asset type: full-screen portrait background for the Chinese app 围桌 service homepage. Generate a polished, quiet tabletop gathering scene in warm ivory #f1f3eb, pale sage #dbe9de, emerald green and small brass accents, matching a friendly offline tabletop scorekeeper. Portrait 2:3 composition. Very light soft textured ivory center occupying 75% of image must remain calm and empty for real interactive UI, not a mockup. Corners contain subtle softly rendered wooden table edge, a few mahjong tiles and playing cards without currency, dice, a small emerald felt detail and warm natural light. Decorative objects only near outer corners and edges, no objects through center. Tasteful soft 3D illustration, clean premium application backdrop, low contrast, no lettering, no logo, no buttons, no watermark. Must work behind dark green readable text and cream cards.

## 宣传启动页提示

Use case: ads-marketing. Asset type: portrait launch poster for 围桌, a friendly local-network scorekeeper for real offline tabletop gatherings. Portrait 2:3 polished soft 3D editorial illustration. Warm ivory #f1f3eb background, pale sage, deep emerald, gentle brass accents, matching a calm app with cream cards and dark green text. Hero in middle: small round emerald table, three simple colorful empty chairs in coral mustard turquoise, two playing cards and mahjong tiles, warm soft shadows. Keep all important illustration and typography inside central 65% width and central 65% height to safely crop on tall iPhone screens; far edges contain only quiet pale texture and faint leaves. Elegant balanced brand composition. Clear Chinese typography, exact text only: large title "围桌" above illustration; subtitle "线下游戏，线上记分" below illustration; smaller supporting line "仅需局域网 · 无需互联网" below subtitle. No fake UI, no buttons, no currency, no casino lights, no people, no additional text, no watermark. Text should be crisp accurately readable with natural Chinese letter spacing.


## v2 背景编辑提示

Edit target: supplied service homepage background. Change only game props: remove every mahjong tile and all mahjong symbols from the top-right and bottom-right corners. Replace top-right props with a small corner of a generic wooden boardgame board and two or three colored wooden pawns; replace bottom-right tile with two wooden hexagonal game tokens and one small ivory die showing a coherent arrangement of dots. Keep the warm ivory and sage palette, leaves, teacup, lighting, wood table edges, portrait composition and large quiet empty center unchanged. Existing playing cards may remain. Absolutely no mahjong tiles or mahjong lettering anywhere. No text, logo, interface, or watermark. Calm family boardgame theme.

## v2 宣传页编辑提示

Edit target: supplied 围桌 launch poster. Change only objects on the green round tabletop: remove ALL three mahjong tiles and every mahjong symbol. Place a small tasteful generic boardgame board with hexagonal wooden spaces, a few emerald/coral/mustard wooden pawn pieces and one ivory die. Two existing playing cards may remain beside the board. Scale these props appropriately for this small round table, preserve the table silhouette and chairs. Absolutely no mahjong tiles or mahjong symbols. Keep all exact existing Chinese text unchanged and crisp: 围桌; 线下游戏，线上记分; 仅需局域网 · 无需互联网. Preserve typography, entire layout, warm ivory/sage palette, lighting, greenery, three colorful chairs, portrait framing. No extra words or UI. Friendly general tabletop gathering theme, no currency, no gambling setting.

## 大厅背景复用

大厅、创建/加入房间与管理员页复用 `service-home-background-v2.webp`，以奶白遮罩降低器物对比度，中心留给文字与真实控件。装饰层固定在视口底层，不接收点击，不因页面内容变长拉伸。手机使用等比例覆盖，电脑使用横向铺满并淡化边缘；牌桌及简约房间保留各自原有背景，不叠加装饰。复用现有约 42 KB 素材，无额外图片下载。
