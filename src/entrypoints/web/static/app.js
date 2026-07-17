(() => {
  const newMenu = document.querySelector("#new-menu");
  const postDialog = document.querySelector("#post-dialog");
  const ideaDialog = document.querySelector("#idea-dialog");
  const sourceText = document.querySelector("[data-preview-source]");
  const mediaInput = document.querySelector("[name='media']");
  const mediaLabel = document.querySelector("[data-media-label]");
  const previewText = document.querySelector("[data-preview-text]");
  const previewPlatforms = document.querySelectorAll("[data-preview-platform]");
  const platformTabs = document.querySelectorAll("[data-platform]");
  const instagramAction = document.querySelector(".post-action--instagram");
  const linkedinAction = document.querySelector(".post-action--linkedin");
  const ideasList = document.querySelector("#ideas-list");
  const ideaForm = document.querySelector("#idea-form");
  const ideasStorageKey = "akashimedia:ideas:v1";

  const openDialog = (dialog) => {
    if (dialog?.showModal) dialog.showModal();
  };

  const closeDialog = (dialog) => {
    if (dialog?.open) dialog.close();
  };

  const closeNewMenu = () => {
    if (newMenu) newMenu.hidden = true;
  };

  document.querySelectorAll("[data-open-new-menu]").forEach((button) => {
    button.addEventListener("click", () => {
      if (newMenu) newMenu.hidden = !newMenu.hidden;
    });
  });

  document.querySelectorAll("[data-open-post]").forEach((button) => {
    button.addEventListener("click", () => {
      closeNewMenu();
      openDialog(postDialog);
      sourceText?.focus();
    });
  });

  document.querySelectorAll("[data-open-idea]").forEach((button) => {
    button.addEventListener("click", () => {
      closeNewMenu();
      openDialog(ideaDialog);
      ideaForm?.elements.idea_title?.focus();
    });
  });

  document.querySelectorAll("[data-close-dialog]").forEach((button) => {
    button.addEventListener("click", () => closeDialog(button.closest("dialog")));
  });

  document.addEventListener("click", (event) => {
    if (newMenu && !newMenu.hidden && !newMenu.contains(event.target) && !event.target.closest("[data-open-new-menu]")) {
      closeNewMenu();
    }
  });

  const setPreviewText = (value) => {
    if (previewText) {
      previewText.textContent = value.trim() || "Текст вашей публикации появится здесь.";
    }
  };

  sourceText?.addEventListener("input", () => setPreviewText(sourceText.value));
  document.addEventListener("input", (event) => {
    if (event.target.matches("[name='linkedin_text']")) setPreviewText(event.target.value);
  });

  platformTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const isLinkedIn = tab.dataset.platform === "linkedin";
      platformTabs.forEach((item) => {
        const active = item === tab;
        item.classList.toggle("is-active", active);
        item.setAttribute("aria-selected", String(active));
      });
      if (instagramAction) instagramAction.hidden = isLinkedIn;
      if (linkedinAction) linkedinAction.hidden = !isLinkedIn;
      if (mediaInput) mediaInput.required = !isLinkedIn;
      if (mediaLabel) mediaLabel.textContent = isLinkedIn ? "Медиа (необязательно для Buffer)" : "Медиа";
      previewPlatforms.forEach((label) => { label.textContent = isLinkedIn ? "LinkedIn" : "Instagram"; });
      const adapted = document.querySelector("[name='linkedin_text']");
      setPreviewText(isLinkedIn && adapted ? adapted.value : sourceText?.value || "");
    });
  });

  document.body.addEventListener("htmx:afterSwap", (event) => {
    if (event.detail.target?.id === "linkedin-adapted") {
      const adapted = event.detail.target.querySelector("[name='linkedin_text']");
      if (adapted) setPreviewText(adapted.value);
    }
  });

  const loadIdeas = () => {
    try {
      const saved = localStorage.getItem(ideasStorageKey);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  };

  const saveIdeas = (ideas) => {
    try {
      localStorage.setItem(ideasStorageKey, JSON.stringify(ideas));
    } catch {
      // The UI still works in the current page if browser storage is unavailable.
    }
  };

  const renderIdeas = () => {
    if (!ideasList) return;
    const ideas = loadIdeas();
    ideasList.replaceChildren();
    if (!ideas.length) {
      const empty = document.createElement("p");
      empty.className = "ideas-empty";
      empty.textContent = "Пока нет сохранённых идей. Зафиксируйте первую, чтобы вернуться к ней позже.";
      ideasList.append(empty);
      return;
    }
    ideas.forEach((idea) => {
      const card = document.createElement("article");
      card.className = "idea-card";
      const meta = document.createElement("div");
      meta.className = "idea-card__meta";
      meta.textContent = "Идея · " + new Date(idea.createdAt).toLocaleDateString("ru-RU");
      const title = document.createElement("h3");
      title.textContent = idea.title;
      const note = document.createElement("p");
      note.textContent = idea.note || "Без заметки";
      card.append(meta, title, note);
      ideasList.append(card);
    });
  };

  ideaForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    const title = String(ideaForm.elements.idea_title.value || "").trim();
    if (!title) return;
    const idea = {
      title,
      note: String(ideaForm.elements.idea_note.value || "").trim(),
      createdAt: new Date().toISOString(),
    };
    saveIdeas([idea, ...loadIdeas()].slice(0, 30));
    ideaForm.reset();
    closeDialog(ideaDialog);
    renderIdeas();
  });

  renderIdeas();
})();
