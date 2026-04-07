# A.1.3: Case Study #3: Datasets & Risks

## _The Building Blocks & Guardrails_

<div style="height:1.5rem"></div>

_Note 1: This outline provides guidance specific to Case Study #3, complementing the **general case study rubric**_ [**[link]**](casestudy.html).  
_Note 2: See lecture note 3.1 **Datasets & Risks of AI** [**[link]**](piii_data_and_risks.html) for some illustrative examples of the tasks._

<div style="height:4rem"></div> 

<hr style="height: 6px; border: none; background-color: #000;">

<div style="height:1.5rem"></div> 

## The Brief

<div style="height:1.5rem"></div> 

Understand how the training dataset guides the **capability and boundary** of a Generative AI model.

Investigate how specific training datasets can differentiate the capability of Generative AI (GenAI) models or LLMs.

You are **NOT training customized Generative AI models.**  
You are **exploring the boundaries of market-ready GenAI/LLMs in specific tasks** (domain knowledge).

<div style="height:1.0rem"></div>

**Examples:**

• It can be asking a pre-trained LLM to generate **"realistic" nighttime images** based on given input daytime images (download daytime images from the [**[link]**](https://drive.google.com/drive/folders/1m0xVRcC5Xi9d1zxKCypMNZ5+XoNF4-?usp=sharing))

• Or you can think about **another specific task in your domain of study** that you notice current LLMs on the market cannot handle well, but through very specific prompts or better datasets, they might improve their capabilities.

Your analysis should address the following questions.

<div style="height:0.5rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.0rem"></div>

### 1. What is the domain-specific task?

(E.g., creating realistic nighttime street view images from daytime ones instead of generating a fancy rendering or fantasy-like visions)

<div style="height:1.0rem"></div>

• **Problem / Function**

&nbsp;&nbsp;&nbsp;&nbsp;– What is the **main objective** of the task?  
&nbsp;&nbsp;&nbsp;&nbsp;– Why is this problem important?  
&nbsp;&nbsp;&nbsp;&nbsp;– Why LLM (or GenAI) might be useful?

<div style="height:0.5rem"></div>

---

<div style="height:1.0rem"></div>

### 2. What models do you use for the task?

(E.g., Do you generate the nighttime images with StableDiffusion, Nano Banana, Midjourney, etc.?)

<div style="height:1.0rem"></div>

• **Model Dependency**

&nbsp;&nbsp;&nbsp;&nbsp;– Describe clearly how it **operates**.  
&nbsp;&nbsp;&nbsp;&nbsp;– Explain how the overall task breaks down into **input data preparation, prompt (or algorithmic steps), and output steps**.

• **Your explanation should show**

&nbsp;&nbsp;&nbsp;&nbsp;– The **overall workflow**  
&nbsp;&nbsp;&nbsp;&nbsp;– The **specific model's mechanism** you are leveraging (E.g., if you are using StableDiffusion, explain how the Diffusion architecture works)  
&nbsp;&nbsp;&nbsp;&nbsp;– The full **Inputs → transformations → outputs link**

<div style="height:0.5rem"></div>

---

<div style="height:1.0rem"></div>

### 3. Is the GenAI model (or LLM) powerful in fulfilling the domain-specific task?

(E.g., mimicking a realistic nighttime urban environment?)

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

&nbsp;&nbsp;&nbsp;&nbsp;– Where helpful, compare the **"initial results"** to an **"improved result"** from an alternative model, or an improved prompt, or feeding in specific training data.

Your analysis should reveal **one key insight** about how the domain-specific training dataset/prompt/harness reshapes model performance.

<div style="height:1.0rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.0rem"></div>

### What a Strong Submission Demonstrates

<div style="height:1.0rem"></div>

A strong submission will:

- Isolate the role of the **training dataset quality** from the mechanism clearly  
- Diagram the **overall workflow of the model**  
- Zoom into the **selected module** (training dataset/prompt/etc)  
- Identify **inputs → transformations → outputs**  
- Explain how the **training dataset matters to behavioral outcomes**

Your writing should demonstrate **training dataset engineering thinking or prompt engineering thinking**.

<div style="height:1.5rem"></div>

<hr style="height: 3px; border: none; background-color: #000;">

<div style="height:1.5rem"></div>
