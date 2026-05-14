---
page_id: '567279621'
title: mentorAI Settings & Options
aliases: []
source_url: https://answers.atlassian.syr.edu/wiki/spaces/ITSAI/pages/567279621/mentorAI+Settings+&+Options
space_key: ITSAI
space_name: Artificial Intelligence (AI)
space_type: knowledge_base
space_category: knowledge-bases
ancestor_path:
- AI @ Syracuse University
- AI
- Clementine Platform
last_modified: '2026-03-30T17:34:17.917Z'
version: 11
contributors:
- 712020:4c323a6a-283a-4261-80da-1e662db12cda
- 712020:882951bc-9249-4b41-8242-4d19030b3116
- 712020:c7102643-0a1c-4d26-bf2d-35eadbd37848
contributors_count: 3
content_hash: sha256:275224da5cc66c57b2294c882f5c607caedcaf9648ad419cd1c61c67e1e9a7c2
synced_at: '2026-05-13T16:56:02Z'
last_sync_status: ok
labels: []
audience: null
doc_type: null
tools: []
topics: []
days_since_modified: 43
maintenance_signal: fresh
conversion_warnings: []
---

Use **Settings & Options** to customize how your mentorAI looks, behaves, and interacts with users. Each setting helps tailor your mentors purpose, audience visibility, and engagement style.

## 🧭 **Edit Mentor Overview**

The **Edit Mentor** panel is where you manage and customize every aspect of your mentorAI. Each tab focuses on a different part of your mentors behavior, visibility, or capabilities  from basic setup to advanced integrations.

**Available Tabs:**

- **⚙️ Settings:** Define your mentors name, description, category, and visibility permissions.
- **🧠 LLM:** Choose which AI model your mentor uses and fine-tune its intelligence level.
- **💬 Prompts:** Configure default, proactive, and guided prompts that shape how the mentor interacts with users.
- **🛡️ Safety:** Adjust moderation filters and set behavior limits to ensure safe, respectful interactions.
- **❗ Disclaimers:** Add custom messages or disclaimers for transparency and ethical guidance.
- **🔧 Tools:** Connect your mentor to additional functions or APIs to enhance its capabilities.
- **🧩 Memory:** Manage what information your mentor retains or recalls during conversations.
- **🕓 History:** View and manage recent interactions for monitoring or improvement.
- **📊 Datasets:** Upload or connect data sources your mentor can reference for more tailored responses.
- **🖥️ Embed:** Generate code to embed your mentorAI directly into web pages or digital platforms.

---

## **⚙️ Settings**

![[attachments/567279621/Screenshot 2025-11-10 at 1.04.00 PM.png|760]]

| **Setting Options** | **Functions, Examples  Tips** |
| --- | --- |
| **🧠 Name** | **What it does:** Defines the mentors display name  this is how users will identify and search for it.   **Example:** *Research  Innovation MentorAI*   **Tip:** Choose a name that clearly communicates the mentors focus area or purpose. |
| **🗒️ Description** | **What it does:**Outlines what the mentor does, who it supports, and how it helps.   **Example:**Supports students in developing creative, well-structured academic and project ideas   **Tip:** Write in a short paragraph, focusing on the mentors *function* and *value* to students. |
| **🧭 Category** | **What it does:**Groups your mentorAI into a specific domain or topic area, like AI Assistance, Advisor or Artificial Intelligence.   **Example:** *AI Assistance* for AIs supporting research, tech, or data-related questions. |
| **👁️ Who Can View?** | **What it does:**Controls which users can see this mentorAI in the directory.   **Options include:**  - **Students:** Visible only to current students - **Administrators:** Visible to staff and admin users - **Anyone:** Publicly accessible |
| #### 💬 Who Can Chat? | **What it does:**   Determines who can start conversations with your mentorAI.   **Options:**  - **Authenticated Users:** Requires campus login (safest option for university AIs) - **Anyone:** Open access (ideal for public-facing mentors) |
| **💾 Save** | **What it does:**Saves all entered information.   **Note:** Make sure each required field (marked with a red asterisk *) is filled in before saving. |

---

## **🧠 LLM**

The **LLM tab** lets you choose the underlying AI model that powers your mentorAI. Different providers offer their own models  such as **Google's** **Gemini**, **OpenAIs** **ChatGPT**, and **Anthropics Claude**  each with unique strengths and response styles.

> [!note]- ⚖️ Why Choose Different LLM Types
> | **🤖 ChatGPT (OpenAI)** | Great for structured reasoning, academic QA, and professional dialogue. Provides balanced performance and clear communication. |
> | --- | --- |
> | **🌐 Gemini (Google)** | Excels in research, data interpretation, and multimodal reasoning (text + image). Ideal for analytical or innovation-based mentors. |
> | **📚 Claude (Anthropic)** | Strong at long-form writing, nuanced reflection, and summarization. Useful for writing support, analysis, or ethics-focused mentors. |

> [!note]- 🧩 Tips for Syracuse MentorAI Use
> - Choose the LLM that fits the **style and purpose** of your mentor.
> - You can switch between models at any time to explore different response styles and performance levels.

> [!info]
> The LLM determines how your mentorAI thinks and communicates. Different models may vary in tone, creativity, and depth of reasoning  try different ones to see what works best for your use case.

---

## **💬 Prompts**

![[attachments/567279621/Screenshot 2025-11-10 at 1.04.08 PM.png|760]]

| **🧱 System Prompt** | **⚡ Proactive Prompt** | **🧭 Guided Prompt** |
| --- | --- | --- |
| **Use:** Establishes the mentors overall purpose and tone. Think of it like a job description for the mentor. | **Use:** A short, automatic message that welcomes or engages users when a chat begins. | **Use:** Offers ready-made suggestions for users to click and start a conversation. |
| **Use this for:** Describing the mentors role and how it should support users. | **Use this for:** Inviting users to ask questions or share what they need help with. | **Use this for:** Common actions or student questions such as Help me plan my essay or Explain this concept. |
| **Tip:** Keep it focused on what the mentor can do for the intended audience. | **Tip:** Keep it friendly, short, and open-ended. | **Tip:** Add prompts that match common campus topics or student tasks. |

**💬 Suggested Prompts**appear as *conversation starters* at the bottom of your mentorAI chat window.
These help users begin a conversation faster by suggesting common or useful questions related to the mentors topic.

> [!info]
> **💡 Tip:**Keep suggested prompts short and action-oriented  they work best when they feel like questions the mentors intended audience would naturally ask (e.g., Find sources for my topic or Help me summarize this reading).

---

## **🛡️ Safety**

The **Safety tab** allows you to set moderation and safety rules for your mentorAI. These settings make sure that all conversations stay appropriate, inclusive, and aligned with Syracuse Universitys standards for respectful communication.

![[attachments/567279621/Screenshot 2025-11-10 at 1.04.19 PM.png|760]]

#### ⚖️ Moderation  Safety Settings

Each safety feature works together to filter, flag, and respond to inappropriate or sensitive interactions:

> [!note]- Moderation Prompt  Reponse
> - **Moderation Prompt:**
>   Describes what types of *user messages* should be flagged  such as hate speech, discrimination, or personal attacks.
> - **Moderation Response:**
>   The message shown to users if their input violates guidelines. It reminds them to stay respectful and may include campus contact info (e.g., *Barnes Center at 315-443-8000* for confidential support).

> [!note]- Safety Prompt  Reponse
> - **Safety Prompt:**
>   Outlines what types of *AI responses* should be restricted  for example, messages that provide medical, legal, or financial advice.
> - **Safety Response:**
>   The message displayed when the AI blocks an unsafe or off-topic question, encouraging users to seek help from appropriate campus resources instead.

> [!info]
> **💡 Tip:**Keep both prompts and responses professional, concise, and student-focused. Together, they create a balanced safety system  filtering inappropriate messages while redirecting students to the right campus support when needed.

---

## ❗ Disclaimers

The **Disclaimers tab** allows you to add advisory messages that appear above the chat window. These short notices remind users to review responses critically and understand the AIs limitations.

![[attachments/567279621/Screenshot 2025-11-10 at 1.04.26 PM.png|697]]

---

## **🔧 Tools**

The **Tools tab** lets you manage what additional resources your mentorAI can access while responding to users.

Find additional information here: [[700121089 - mentorAI - Tools]]

![[attachments/567279621/Screenshot 2025-11-10 at 1.04.35 PM.png|760]]

> [!note]- 🗂️ Using Trained Documents?
> Enables the mentorAI to use materials connected in the **Datasets** section.
> **Use this for:** Allowing the mentor to reference specific documents or files (e.g., campus guides, program FAQs, or academic resources).
> **Tip:** Keep this enabled if your mentor is meant to give context-specific guidance based on uploaded or approved materials.

> [!note]- 🌐 Using Web Search?
> Allows the mentorAI to search the internet for up-to-date information beyond its trained data.
> **Use this for:** Providing current information, resources, or examples that may not be in the dataset.
> **Tip:** Turn this off if you want the mentor to rely only on approved Syracuse-related materials.

---

## **🧩 Memory**

The **Memory tab** is designed to let mentorAI store and reference helpful information from past interactions.

![[attachments/567279621/Screenshot 2025-11-10 at 1.04.44 PM.png|760]]

> [!note]- 🗂️ Memory Categories
> Each saved memory can be sorted into a category for better organization:
>
> - **Personal Information:** Notes about user context, preferences, or goals (only when appropriate and privacy-safe).
> - **Lessons Learned:** Reflections or takeaways from past interactions.
> - **Help Requests:** Information about recurring questions or support topics students ask for.
> - **Knowledge Gaps:** Areas where users often need clarification, helping mentors improve future responses.

> [!note]
> #### This feature is currently experimental. As mentorAI continues to evolve, memory will allow mentors to adapt to student needs more effectively while maintaining Syracuse Universitys privacy and data protection standards.

---

## **🕓 History**

The **History tab** allows you to view and manage all past conversations with your mentorAI. This includes reviewing chat logs, filtering interactions by topic or sentiment, and tracking overall engagement trends.

![[attachments/567279621/Screenshot 2025-11-10 at 1.04.54 PM.png|760]]

> [!note]- 📊 Key Features
> 1. **User Search:** Filter past conversations by specific users.
> 2. **Date Range:** Narrow results to a specific period for analysis.
> 3. **Sentiment  Topics:** Review how students felt about the conversation and what subjects came up most often.
> 4. **Export Option:** Download interaction data for review or reporting.
> 5. **Rating System:** Displays an overall score (out of 5). A higher rating indicates better user satisfaction and response quality.

**Note:** New mentorAIs will have no conversation data or ratings are available. Once more users begin using the mentor, this section will increasingly help track engagement and mentor effectiveness

---

## **📊 Datasets**

The **Datasets tab** allows you to manage the training materials and knowledge sources your mentorAI can reference while responding to users. By connecting files, links, or cloud resources, you can help the mentor provide accurate, context-specific guidance for students.

![[attachments/567279621/Screenshot 2025-11-10 at 1.05.14 PM.png|760]]

### 📄 Supported Data Types

| **Type** | **Function** | **Limitations / Notes** |
| --- | --- | --- |
| **PowerPoint / PDF / DOCX / TXT / Excel** | Pulls readable text, titles, and notes to use as knowledge references. | Cannot read images, charts, or handwritten notes inside slides. |
| **Google Drive / OneDrive / Dropbox** | Connects directly to stored files in the cloud for continuous access. | Access permissions must allow mentorAI to view the file. |
| **URL / Web Crawler** | Uses website content to gather updated information or academic resources. | Must be a text-based site (not image-heavy or behind a login). |
| **YouTube / Video / Audio** | Uses transcripts or captions to extract educational or research-related information. | Requires transcript or subtitles to tokenize. |
| **GitHub** | Useful for research or coding-related projects where the mentor references repositories. | Reads text-based files only (like `.py`, `.md`, or `.txt`). |
| **Image / ZIP** | Reads any text metadata or OCR-extracted text (if available). | Cannot analyze the visual content itself. |
| **Web Crawlers** | Scans linked pages within a provided URL to gather additional related content. | Only captures textual updates, not images or media. |

> [!info]
> **💡 Tip:** To make the most of your dataset uploads, prioritize resources with **text-based content** like websites, PDFs, and guides. This ensures the mentors responses stay relevant and academically grounded.

---

## **🖥️ Embed**

The **Embed** section allows you to configure how your mentorAI appears and functions when placed on a website or within another digital platform. This includes visual customization, permissions, and interactive features.

![[attachments/567279621/Screenshot 2025-11-10 at 1.12.34 PM.png|760]]

### ⚙️ Core Features

| **Setting** | **Function** | **Notes / Example** |
| --- | --- | --- |
| **Advanced CSS** | Lets you style the mentor widget with custom CSS (colors, fonts, borders, etc.). | For advanced customization  ideal for matching SUs brand style. |
| **Icon Selection** | Choose between a default icon or upload a **custom icon** (logo or mascot). | The icon shown in the **Live Preview** at the bottom right corner. |
| **Mode Selection** | Switch between **Default** and **Advanced** modes. | Default = simple chat only. Advanced = adds tabs like *Summarize*, *Translate*, and *Expand*. |
| **Who Can View** | Restrict visibility to **Students**, **Administrators**, or **Anyone**. | Most mentors should be set to **Students** (all university members are considered students in MentorAI).   Select this option and the Who Can Chat option to **Anyone** to allow anonymous users, useful for public or website chatbots.   *(Options may change in future updates.)* |
| **Who Can Chat** | Limit who can actively interact: **Anyone** or **Authenticated Users** (those signed in). | Useful if your site requires SU NetID or another login. |
| **Website URL** | The web address where the mentor will be embedded. | Used for generating a unique embed token tied to that domain. |
| **Get Token** | Generates an authentication token that allows the chat to run securely on that URL. | Likely required for linking the embed to an official SU page. |
| **Context Aware** | Enables the mentor to use the website context (like the page topic) when answering. | Good for mentors hosted on resource pages or help sites. |
| **Single Sign-On (SSO)** | Integrates with campus authentication so users dont need to log in separately. | May be used by the IT department. |
| **Open by Default** | Makes the chat window automatically open when a user loads the page. | Helpful for welcome messages or proactive engagement. |
| **Show Attachment** | Adds an option to upload or attach files directly in chat. | Ideal for sending PDFs, docs, or screenshots. |
| **Show Voice Call / Record** | Enables audio interaction  either real-time calling or voice message recording. | Still experimental in many mentor setups. |
| **Shareable Link** | Generates a public link to share the chat outside the embedded site. | Useful for testing or sharing with teammates. |
| **Create Embed** | Finalizes all chosen settings and generates a **code snippet** (HTML `script` or `iframe`) for embedding on your chosen website. | This is code that a web developer or IT admin can use to add the mentor to a website. |

---

## ❓ Frequently Asked Questions (FAQ)

> [!note]- Can MentorAI access or remember personal information from users?
> No. mentorAI does not automatically store personal data. Any saved memory must be manually added under the **Memory** tab by an administrator or creator/owner of a mentor.

> [!note]- Why isnt my dataset working or showing up in responses?
> mentorAI can only process text-based content. If your file or link mostly contains images or lacks visible text (like a scanned PDF), it wont be tokenized properly.

> [!note]- What does token count mean in the Datasets section?
> Tokens represent chunks of readable text that the AI has processed. More tokens generally mean more data for the mentor to reference.

> [!note]- Whats the difference between Web Search and Trained Documents?
> *Trained Documents* come from your uploaded datasets, while *Web Search* lets the mentor pull current information from the internet when responding.
