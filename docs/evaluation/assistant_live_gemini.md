# Assistant live evaluation (gemini, 2026-11-22)

> Live calls to the configured LLM on the demo farm (real weather/soil, hypothetical farm).
> 6 questions is a smoke test, not a statistically meaningful evaluation. Answers are shown
> for human review: the grounding check verifies numbers and citations, not usefulness.

- Questions: 6 (2 per language). Verified by the grounding check: 6/6. Template fallback: 0/6.
- Median latency 38.8 s (max 130.1 s).

| lang   | verified   | fallback   | fallback_reason   |   violations | tools                                                      |   latency_s | model                 | q                                             |
|:-------|:-----------|:-----------|:------------------|-------------:|:-----------------------------------------------------------|------------:|:----------------------|:----------------------------------------------|
| en     | True       | False      |                   |            0 | list_decisions, get_decision                               |        22.7 | gemini-3.5-flash-lite | What should I do first today, and why?        |
| en     | True       | False      |                   |            0 | list_decisions, compare_priority                           |       122.3 | gemini-3.5-flash-lite | Why is the tomato zone ranked above the potat |
| fr     | True       | False      |                   |            0 | list_decisions, get_decision, list_decisions, get_decision |       130.1 | gemini-3.5-flash-lite | Combien d'eau faut-il pour la zone tomate et  |
| fr     | True       | False      |                   |            0 | get_anomalies, get_anomalies                               |         7.3 | gemini-3.5-flash-lite | Y a-t-il une fuite ou une anomalie sur mon ré |
| ar     | True       | False      |                   |            0 | list_decisions, get_decision                               |        54.9 | gemini-3.5-flash-lite | ما هي أولوية الري اليوم ولماذا؟               |
| ar     | True       | False      |                   |            0 | get_suitability                                            |         5.7 | gemini-3.5-flash-lite | هل الطماطم مناسبة لمزرعتي؟                    |

## Answers

### [en] What should I do first today, and why?

Your highest-priority action today is to **irrigate `tomato-east` with `120` m³** [r1, r2]. 

**Why:**
- **Irreversible risk:** The root zone is already beyond the stress threshold (root-zone depletion is `64.89` mm against a readily available water level of `21.7` mm) [r2].
- **Expected impact:** This proposal avoids `1284.3` mm h of stress [r2]. 

**Data and limitations:** 
- This recommendation comes from the model (`inferred` data class) with **medium** confidence [r1, r2]. 
- **Main limitation:** Parameters are international reference values, not calibrated for Tunisian varieties or practices, and the model relies on projected PV energy [r1, r2]. 
- *Note:* All irrigation proposals require your approval before any action is carried out [r1, r2].

_violations:_ none

### [en] Why is the tomato zone ranked above the potato zone?

The tomato zone (`tomato-east`, package `demo-farm-1`) ranks above the potato zone (`potato-south`, package `demo-farm-2`) because they belong to different priority tiers under QATRA's lexicographic ranking rule [r1, r2]. 

The tomato decision is in **Tier 1 (irreversible risk)** due to a sensitive crop stage ($K_y$ 1.1) and stress within 1 day, whereas the potato decision is in **Tier 2 (stress within horizon)** [r2]. QATRA prioritizes packages strictly by tier, then by time to stress, and then by avoided stress per cubic meter [r2]. 

This information comes from QATRA's inferred decision engine (`data_class: inferred`) with medium confidence [r1, r2]. The main data limitation is that these rankings are model-simulated proposals and physical irrigation requires human approval [r1].

_violations:_ none

### [fr] Combien d'eau faut-il pour la zone tomate et quand ?

Pour la zone de tomates (`tomato-east`), QATRA propose d'irriguer pour un montant de **120** m³ [r3, r4]. 

* **Quand ?** Dès maintenant, dans les fenêtres horaires débutant à partir de **2025-06-15 00:00** jusqu'à **16:00** [r4].
* **Pourquoi ?** La zone racinaire est déjà au-delà du seuil de stress [r4].

Cette information provient d'un modèle inféré (méthode modelée sans capteur d'humidité du sol) avec un niveau de confiance moyen [r4]. La principale limite est que les paramètres sont des valeurs de référence internationales non calibrées pour les variétés ou pratiques tunisiennes [r4]. 

*Note : Cette recommandation nécessite l'approbation d'un opérateur [r3, r4].*

_violations:_ none

### [fr] Y a-t-il une fuite ou une anomalie sur mon réseau ?

Plusieurs anomalies (basées sur des données simulées avec une confiance moyenne à faible) ont été détectées sur votre réseau [r2] :

* **Fuites et débits lents :** Des anomalies de type fuite lente ont été enregistrées, totalisant par exemple 50,6 m³ sur 83 h ou 20,3 m³ sur 105 h [r2].
* **Excès de débit :** Un excès de débit a été relevé (51,9 m³ mesurés contre 37,4 m³ attendus) sur la zone B, accompagné d'une baisse de pression [r2].

**Vérifications recommandées :**
* Inspecter les raccords, les sièges de vannes et les zones actives pour déceler d'éventuelles ruptures ou fuites [r2].
* Vérifier la fermeture de chaque vanne de zone [r2].

_violations:_ none

### [ar] ما هي أولوية الري اليوم ولماذا؟

القرار الأول والأهم للري اليوم هو **ري قطعة الطماطم الشرقية (tomato-east)** بكمية مقترحة تبلغ **120** متراً مكعباً [r1, r2].

**السبب الرئيسي:**
منطقة جذور النبتة تجاوزت عتبة الإجهاد المائي حالياً [r2].

**معلومات إضافية:**
- هذه البيانات مستنتجة (inferred) وليست مقياسة بمستشعرات أرضية، ومستوى الثقة متوسط [r1, r2].
- تعتمد المعلمات على قيم مرجعية دولية وليست معايرة محلياً [r2].
- هذه توصية مقترحة تحتاج إلى موافقة بشرية قبل أي تنفيذ [r1, r2].

_violations:_ none

### [ar] هل الطماطم مناسبة لمزرعتي؟

بناءً على تقييم الملائمة الزراعية (بصيغة محاكاة ذات موثوقية استدلالية ومستوى مراجعة يحتاج إلى تدقيق)، فإن الطماطم مصنفة بشكل عام كـ **S3 (ملائمة ضعيفة)** لمزرعتك [r1]. 

وإليك التفاصيل الأساسية:
- **المياه (عامل محدد رئيسي):** التصنيف هنا هو S3؛ حيث تتوفر 6000 متر مكعب بينما تبلغ الكمية المطلوبة 11083 متر مكعب/هكتار (في سنة جافة P80)، مما يتيح عائداً نسبياً متوقعاً بنسبة 52.3% [r1].
- **الحرارة:** التصنيف N (غير ملائم) مع وجود تحذير مؤقت؛ لأن عتبة الحرارة عبارة عن مؤشر مؤقت غير مدقق (تصل أيام الحرارة المرتفعة Tmax > 35° إلى 31.8 يوماً في الموسم) [r1].
- **عوامل أخرى:** الطاقة مصنفة S1 (متوفرة بـ 1981 كيلوواط ساعة/هكتار للضخ) [r1]، والملوحة (ECe 2.2 ديسيسيمنز/متر) وعمق التربة مصنفتان S1 [r1]، بينما لم يتم دمج بيانات السوق بعد (U) [r1]. 

يُرجى ملاحظة أن المعلمات الخاصة بالمحصول ومعايير درجات الحرارة لا تزال بحاجة إلى مراجعة وتعتمد على عتبات غير مؤكدة [r1].

_violations:_ none
