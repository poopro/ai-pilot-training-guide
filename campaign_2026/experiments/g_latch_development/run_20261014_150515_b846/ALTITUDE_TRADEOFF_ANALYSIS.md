# 高度退步與攻擊不足：已保存遙測分析

僅讀取既有CSV、result與來源；沒有新FDM、verifier、訓練、Host或外傳。此候選仍不宜部署。

最差為rule／3000ft／mirrored／seed 2026101400，兩側initial SHA完全相同，完整共同300秒。candidate的G latch全程0tick。

| 時點 | 精確觀察 |
|---|---|
| 0.016667秒／tick1 | bank target：guide72°、candidate80°；舵面相同。 |
| 0.350000秒／tick21 | 第一個副翼命令差異：guide0.9540773712、candidate1.0；elevator/rudder/throttle仍相同。tick20觀測與舵面相同。 |
| 150秒 | guide高度2634.950429m、candidate2646.120072m；candidate仍高11.169642m。 |
| 150–180秒 | guide下降138.250945m、candidate下降278.221311m；candidate多失139.970366m。 |
| 154.666667秒 | candidate進track，d1091.902m、CAS462.493節、pitch target−13.665°；guide仍intercept，d1129.960m、target−0.834°。 |
| 156秒 | candidate roll82.162°、guide75.319°，CAS442.820／440.714節；candidate目標bank80°但trim計算上限75°。 |
| 158.133333秒起 | candidate離開track後直到300秒全程intercept；此刻d1106.476m、roll79.569°、CAS409.501節。 |
| 180秒 | candidate d4982.669m、CAS300.014節、roll69.176°；guide d1755.941m、CAS402.354節、roll−36.269°。 |
| 270–300秒 | guide全程track並上升26.512599m；candidate全程intercept並下降200.525603m，額外高度變化−227.038202m。 |
| 各自最低HSL高度 | guide1794.573623m＠275.500000s；candidate1475.255270m＠300.000000s；差-319.318352m。 |

150–180秒內，Bank80實際binding僅在154.666667–158.116667秒的208tick；此後為intercept，bank ceiling已回72°。270–300秒完全沒有Bank80 binding。晚期多失高度是在已分歧的追擊位置與mode下發生，不能說它仍持續命令80°轉彎。JSON提供兩段每5秒的双邊CAS／roll／pitch／bank target／distance／closing／altitude與mode。

這條因果鏈只確認第一個控制差異來自近距離bank ceiling。後續俯仰、速度、交戰位置、對手反應與mode切換已分歧，不能把整段高度差歸因於一次高bank，也不能歸因於未啟動的latch。

下一個可測單因素：近距離bank ceiling80→75，其他設定全部保留。先回歸最差3000 mirrored及最高攻擊RL9000 mirrored；若高度差未改善，或RL攻擊降到166tick以下，就不支持此假設。通過後仍须保留current80既有三個rule kill場結果（3000／6000／9000 normal），且零新增墜機／死亡／過9G。禁止blind sweep，不改飛行安全閾值。這是未驗證假設。

RL最高攻擊場為9000ft／mirrored／seed 2026101412。candidate累積166tick＝2.766667秒，四段如下：

| 命中時段 | tick數 | 秒數 |
|---|---:|---:|
| 115.516667–116.350000秒 | 51 | 0.850000 |
| 126.950000–127.783333秒 | 51 | 0.850000 |
| 138.166667–138.883333秒 | 44 | 0.733333 |
| 149.200000–149.516667秒 | 20 | 0.333333 |

每段退出後仍在合法距離（約692／686／669／653m），但機鼻角由≤1°跨到1.004092／1.009824／1.005694／1.000838°，所以暫停增加攻擊時間。已保存攻擊計數沒有下降或重置；累積還差14tick＝0.233333秒才滿180tick。六場總5.066667秒不能跨場拼成擊殺。

已核對凍結來源：DiagnosticJudge.update以`self.attack[0] += int(window)`逐tick累加；離開window沒有歸零，LocalJudge.outcome在TARGET_FRAMES＝3×60＝180判kill。跨段累積符合現有judge，並非假設需要連續3秒。JSON保留這些函式與SHA。

JSON保留30秒區間、精確狀態、mode連續區間、command/act來源差異、SHA與攻擊段邊界。遙測為step後狀態；本tick命令由前一個tick觀測計算，避免把同一列後狀態當作命令輸入。
鏡像開局是本地測試設計，不等於官方P1/P2角色交換；所有成績為開發資料。
