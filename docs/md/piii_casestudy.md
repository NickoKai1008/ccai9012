# A.1.3: Case Study #3: Datasets & Risks

## _The Building Blocks & Guardrails_

<div style="height:1.5rem"></div>

_Note 1: This outline provides guidance specific to Case Study #3, complementing the **general case study rubric**_ [**[link]**](casestudy.html).  
_Note 2: See lecture note 3.1 Datasets & Risks of AI_ [**[link]**](pii_examples.html) _for some illustrative examples of the tasks._

<div style="height:4rem"></div> 

<hr style="height: 6px; border: none; background-color: #000;">

<div style="height:1.5rem"></div> 

## The Brief

<div style="height:1.5rem"></div> 

Understand how the training dataset guides the **capability and boundary** of a Generative AI model.

Investigate how specific training datasets can differentiate the capability of Generative AI (GenAI) models or LLMs.

You are **NOT training customized Generative AI models.**  
You are **exploring the boundaries** of market-ready GenAI/LLMs in specific tasks (domain knowledge).

- It can be asking a pre-trained LLM to **generate "realistic" nighttime images based on given input daytime images** (download daytime images from the [**link**](https://drive.google.com/drive/folders/1m0xVRvCSXI9uI1zXKCypMNZ5-kXnNF4-?usp=sharing))

- Or you can think about **another specific task in your domain of study** that you notice current LLMs on the market cannot handle well, but through very specific prompts or better datasets, they might improve their capabilities.

Your analysis should address the following questions.
<div style="height:0.5rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.0rem"></div>

### 1. What is the domain-specific task? (E.g., creating realistic nighttime street view images from daytime ones instead of generating a fancy rendering or fantasy-like visions)

<div style="height:1.0rem"></div>

• **Problem / Function**

&nbsp;&nbsp;&nbsp;&nbsp;– What is the **main objective** of the task?  
&nbsp;&nbsp;&nbsp;&nbsp;– Why is this problem important?  
&nbsp;&nbsp;&nbsp;&nbsp;– Why LLM (or GenAI) might be useful?

<div style="height:0.5rem"></div>

---

<div style="height:1.0rem"></div>

### 2. What models do you use for the task? (E.g., Do you generate the nighttime images with StableDiffusion, Nano Banana, Midjourney, etc.?)

<div style="height:1.0rem"></div>

• **Model Dependency**

&nbsp;&nbsp;&nbsp;&nbsp;– Describe clearly **how it operates**.  
&nbsp;&nbsp;&nbsp;&nbsp;– Explain how the overall task breaks down into **input data preparation, prompt** (or algorithmic steps), and **output** steps.

• **Your explanation should show**

&nbsp;&nbsp;&nbsp;&nbsp;– The **overall workflow**  
&nbsp;&nbsp;&nbsp;&nbsp;– The **specific model's mechanism** you are leveraging (E.g., if you are using StableDiffusion, explain how the Diffusion architecture works)  
&nbsp;&nbsp;&nbsp;&nbsp;– The full **Inputs → transformations → outputs** link

<div style="height:0.5rem"></div>

---

<div style="height:1.0rem"></div>

### 3. Is the GenAI model (or LLM) powerful in fulfilling the domain-specific task? (E.g., mimicking a realistic nighttime urban environment?)

<div style="height:1.0rem"></div>

• **Capabilities**

&nbsp;&nbsp;&nbsp;&nbsp;– What strengths or behaviors does the model enable?

• **Limitations**

&nbsp;&nbsp;&nbsp;&nbsp;– What problems or dysfunctionality do you spot/diagnose from the pre-trained model?

<div style="height:0.5rem"></div>

---

<div style="height:1.0rem"></div>

### 4. How do you improve it?

<div style="height:1.0rem"></div>

• **Causal reasoning**

&nbsp;&nbsp;&nbsp;&nbsp;– Explain how training dataset quality, and/or prompt engineering might (or might not) improve the model's ability for the domain-specific task.

• **Comparison**

&nbsp;&nbsp;&nbsp;&nbsp;– Where helpful, compare the **"initial results"** to an **"improved result"** from an **alternative model,** or **an improved prompt,** or **feeding in specific training data**.

Your analysis should reveal **one key insight** about how the domain-specific training dataset/prompt/harness reshapes model performance.

<div style="height:1.0rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.0rem"></div>

### What a Strong Submission Demonstrates

<div style="height:1.0rem"></div>

A strong submission will:

- Isolate the role of the **training dataset quality** from the mechanism clearly  
- Diagram the **overall workflow of the model**  
- Zoom into the **selected module (training dataset/prompt/etc)**  
- Identify **inputs → transformations → outputs**  
- Explain how the **training dataset matters to behavioral outcomes**

Your writing should demonstrate **training dataset engineering thinking** or **prompt engineering thinking**.

<div style="height:1.5rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.5rem"></div>

### Choosing Your Task

Your domain-specific task should be:

- **Specific**  
- **Practically identifiable**  
- **Narrow enough to analyse clearly**  
- **Causally linked to dataset or prompt quality**

Do not choose something broad like **"AI image generation"** or **"language models."**  
Focus on **one clearly defined task** where dataset or prompt choices visibly shape output quality.

Explain the task and model **conceptually**.  
You may reference specific techniques where necessary to clarify how it works.

Do **not** turn this into a technical manual.

**Clarity over breadth.  
Dataset over surface.**

<div style="height:4.0rem"></div> 

<hr style="height: 6px; border: none; background-color: #000;">

<div style="height:2.0rem"></div> 


## Deliverables

<div style="height:1.5rem"></div>

Your submission must include **four parts**.

<div style="height:0.5rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.0rem"></div>

### i. Annotation (≈500 words)

<div style="height:1.0rem"></div>

Provide a short written annotation accompanying your case study.

• **Title**  
&nbsp;&nbsp;&nbsp;&nbsp;– A clear title identifying the task, model, and dataset focus studied.

• **Caption / Description**  
&nbsp;&nbsp;&nbsp;&nbsp;– A brief written explanation summarising the domain task, the model used, and your key finding about dataset or prompt influence.

<div style="height:0.5rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.0rem"></div>

### ii. The Artefact

<div style="height:1.0rem"></div>

Your artefact consists of **two components**:

• **Supporting Explanation** — contextual material that frames the domain task and the model you analyse  
• **Dataset / Prompt Representation** — the core explanation showing how dataset or prompt choices shape outputs  

Think of this as **telling the story of the task first, then revealing how data or prompts drive the result**.

<div style="height:1.0rem"></div>

---

<div style="height:1.0rem"></div>

#### Explanation Layer (Supporting Context)

<div style="height:1.0rem"></div>

This section provides the **context needed to understand the task and model under study**.  
It is essentially the **story or narrative that frames your investigation**.

It may include slides, visual examples, short demonstrations, or other explanatory material.

Your explanation layer should generally follow the sequence below.

• **Problem**  
&nbsp;&nbsp;&nbsp;&nbsp;– Illustrate the real-world domain task the model is being asked to address.

• **System Context**  
&nbsp;&nbsp;&nbsp;&nbsp;– Provide brief background on the GenAI model or LLM being studied.

• **Dataset / Prompt (Overview)**  
&nbsp;&nbsp;&nbsp;&nbsp;– Identify the training data or prompting strategy you will investigate.  
&nbsp;&nbsp;&nbsp;&nbsp;– The detailed explanation follows in the next section.

• **Assessment**  
&nbsp;&nbsp;&nbsp;&nbsp;– Provide preliminary observations about what the model does well and where it fails.

• **Comparison (if relevant)**  
&nbsp;&nbsp;&nbsp;&nbsp;– Introduce any alternative models, prompts, or dataset configurations that may be referenced later.

The goal of this section is to **frame the task and prepare the reader for the detailed dataset/prompt analysis**.

This corresponds to the **contextual slides or images** that accompany your core artefact in the online gallery documentation.

<div style="height:1.0rem"></div>

---

<div style="height:1.0rem"></div>

#### Dataset / Prompt Analysis (Core Artefact)

<div style="height:0.3rem"></div>

This section is the **central focus of the artefact**.

Explain how dataset quality or prompt engineering shapes model outputs using **clear comparative representations**.

Your explanation should make visible:

• The **overall workflow of the model**  
• The **specific dataset or prompt module** you are analysing  
• **Inputs → transformations → outputs**  
• How output quality **changes across different data or prompt conditions**

Where relevant, present **multiple levels of abstraction**:

• **System-level overview** — the overall model pipeline  
• **Data/prompt-level breakdown** — the specific dataset or prompt you selected  
• **Output comparison** — how performance shifts with different inputs  

If the task is complex, focus on the **overall structure plus one clearly analysed dataset or prompt variable**.

The goal is to make the **hidden role of training data legible**.

This is **not a demo of aesthetic outputs** and **not an exercise in visual polish**.

Your priority is **clarity of how data quality or prompt design shapes model behaviour**.

<div style="height:0.5rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.0rem"></div>

### iii. Vignette

<div style="height:1.0rem"></div>

The vignette is a **short-form video presentation** summarising your case study.

• Duration: **approximately 90 seconds**

Your video should clearly communicate:

• The **domain-specific task studied**  
• The **model and dataset/prompt strategy you investigated**  
• Your **key insight about how training data or prompting reshapes model performance**

<div style="height:0.5rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.0rem"></div>


### iv. Evidences (Optional)

<div style="height:1.0rem"></div>

You may include **supplementary materials** in an appendix, such as:

• Code snippets  
• Prompt comparisons  
• Side-by-side output comparisons  
• Additional diagrams or tables  
• Dataset descriptions or samples


<div style="height:4rem"></div> 

<hr style="height: 6px; border: none; background-color: #000;">

<div style="height:1.5rem"></div> 


## Grading Criteria  
<div style="height:1.5rem"></div>

### In a nutshell

#### We are **not** grading:

- Advanced machine learning training  
- Sophisticated model fine-tuning  
- Exhaustive dataset coverage  

<div style="height:1.5rem"></div>

#### We **are** grading:

| Criterion | What It Means |
|-----------|---------------|
| **Understanding** | Do you correctly explain how the model and its training data interact to produce outputs? |
| **Causal Reasoning / Comparison** | Do you link dataset or prompt choices to observable changes in model behaviour, including comparisons across conditions? |
| **Limitations** | Do you identify meaningful failure modes or constraints introduced by the dataset or prompt design? |
| **Clarity** | Can you explain complex ideas in a precise and accessible way? |
| **Visual Explanation** | Do your diagrams or visual representations clearly communicate the workflow and output differences? |

<div style="height:1.5rem"></div> 

### Rubric

| Criterion | Excellent | Adequate | Insufficient |
|-----------|-----------|-----------|--------------|
| **Task & Model Accuracy** | Structurally correct and clearly articulated explanation of the domain task and model used | Mostly correct explanation with minor gaps or simplifications | Superficial, vague, or incorrect description of the task or model |
| **Causal Analysis** | Clear linkage between dataset/prompt design and model output quality, with thoughtful comparison | Some connection between data/prompt and output, but underdeveloped | Describes outputs or observations without causal reasoning |
| **Failure Awareness** | Identifies meaningful limitations, failure modes, or dataset/prompt constraints | Mentions limitations but without depth or explanation | No meaningful discussion of limitations |
| **Clarity of Communication** | Complex task explained clearly and accessibly to non-specialists | Explanation understandable but dense or uneven | Obscure, overly technical, or difficult to follow |
| **Visual Explanation** | Visuals clearly reveal the model workflow, dataset role, and output comparison | Visuals present but only partially clarify the analysis | Visuals absent, confusing, or decorative rather than explanatory |


### Submission Deadline
<s>Original: 📅2026.04.01 ⏰00:00</s>  
Extended: <span style="background-color:#a00000;color:#fff;">📅2026.04.08 ⏰00:00</span>  


<div style="height:1.5rem"></div> 

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.5rem"></div> 

## The Standard

<div style="height:1.5rem"></div> 

The goal is not to *use AI tools*.  
The goal is to **understand what shapes their outputs**.

Do not remain at the surface of generated images or text.  
Demonstrate that you can think in datasets, prompts, and model pipelines.

Don't just run AI.  
**Interrogate it.**
