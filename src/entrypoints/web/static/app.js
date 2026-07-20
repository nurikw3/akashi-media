(() => {
  const themeStorageKey = "akashimedia:theme:v1";
  const themeToggles = document.querySelectorAll("[data-theme-toggle]");
  const savedTheme = (() => {
    try {
      return localStorage.getItem(themeStorageKey);
    } catch {
      return null;
    }
  })();

  const setTheme = (theme) => {
    const normalizedTheme = theme === "light" ? "light" : "dark";
    document.documentElement.dataset.theme = normalizedTheme;
    const isDark = normalizedTheme === "dark";
    themeToggles.forEach((toggle) => {
      const label = toggle.querySelector("[data-theme-label]");
      const icon = toggle.querySelector("[data-theme-icon]");
      const action = isDark ? "Включить светлую тему" : "Включить тёмную тему";
      toggle.setAttribute("aria-label", action);
      toggle.setAttribute("title", action);
      toggle.setAttribute("aria-pressed", String(!isDark));
      if (label) label.textContent = isDark ? "Светлая" : "Тёмная";
      if (icon) icon.textContent = isDark ? "☀" : "◐";
    });
  };

  setTheme(savedTheme);
  themeToggles.forEach((toggle) => {
    toggle.addEventListener("click", () => {
      const nextTheme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      setTheme(nextTheme);
      try {
        localStorage.setItem(themeStorageKey, nextTheme);
      } catch {
        // Theme still changes for the current page if storage is unavailable.
      }
    });
  });

  const newMenu = document.querySelector("#new-menu");
  const postDialog = document.querySelector("#post-dialog");
  const ideaDialog = document.querySelector("#idea-dialog");
  const aiDialog = document.querySelector("#ai-dialog");
  const aiTask = document.querySelector("[data-ai-task]");
  const aiBrief = aiDialog?.querySelector("[name='brief']");
  const sourceText = document.querySelector("[data-preview-source]");
  const mediaInput = document.querySelector("[name='media']");
  const mediaLabel = document.querySelector("[data-media-label]");
  const dropzone = document.querySelector("[data-dropzone]");
  const fileList = document.querySelector("[data-file-list]");
  const filePreviews = document.querySelector("[data-file-previews]");
  const clearMedia = document.querySelector("[data-clear-media]");
  const mediaGuidance = document.querySelector("[data-media-guidance]");
  const previewMedia = document.querySelectorAll("[data-preview-media]");
  const previewTexts = document.querySelectorAll("[data-preview-text]");
  const networkPreviews = document.querySelectorAll("[data-network-preview]");
  const previewPlatforms = document.querySelectorAll("[data-preview-platform]");
  const platformTabs = document.querySelectorAll("[data-platform]");
  const instagramAction = document.querySelector(".post-action--instagram");
  const linkedinAction = document.querySelector(".post-action--linkedin");
  const postSideTabs = document.querySelectorAll("[data-show-side]");
  const postSidePanels = document.querySelectorAll("[data-side-panel]");
  const postAiBrief = document.querySelector("[data-post-ai-brief]");
  const postAiTask = document.querySelector("[data-post-ai-task]");
  const ideasList = document.querySelector("#ideas-list");
  const ideaForm = document.querySelector("#idea-form");
  const ideasStorageKey = "akashimedia:ideas:v1";
  let selectedMedia = [];
  let mediaObjectUrls = [];

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

  document.querySelectorAll("[data-open-ai]").forEach((button) => {
    button.addEventListener("click", () => {
      closeNewMenu();
      if (aiBrief && sourceText?.value.trim() && !aiBrief.value.trim()) {
        aiBrief.value = "Исходный текст:\n" + sourceText.value.trim();
      }
      openDialog(aiDialog);
      aiBrief?.focus();
    });
  });

  const showPostSide = (name) => {
    postSideTabs.forEach((tab) => tab.classList.toggle("is-active", tab.dataset.showSide === name));
    postSidePanels.forEach((panel) => { panel.hidden = panel.dataset.sidePanel !== name; });
  };

  postSideTabs.forEach((tab) => {
    tab.addEventListener("click", () => showPostSide(tab.dataset.showSide));
  });

  document.querySelectorAll("[data-open-post-ai]").forEach((button) => {
    button.addEventListener("click", () => {
      if (postAiBrief && sourceText?.value.trim() && !postAiBrief.value.trim()) {
        postAiBrief.value = "Исходный текст:\n" + sourceText.value.trim();
      }
      showPostSide("ai");
      postAiBrief?.focus();
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
    previewTexts.forEach((previewText) => {
      previewText.textContent = value.trim() || "Текст вашей публикации появится здесь.";
    });
  };

  sourceText?.addEventListener("input", () => setPreviewText(sourceText.value));

  const formatFileSize = (bytes) => bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} КБ`
    : `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;

  const syncMediaInput = () => {
    if (!mediaInput) return;
    const transfer = new DataTransfer();
    selectedMedia.forEach((file) => transfer.items.add(file));
    mediaInput.files = transfer.files;
  };

  const uniqueFiles = (files) => {
    const seen = new Set();
    return files.filter((file) => {
      const key = `${file.name}:${file.size}:${file.lastModified}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return file.type.startsWith("image/");
    }).slice(0, 10);
  };

  const renderFiles = () => {
    if (!fileList || !mediaInput) return;
    mediaObjectUrls.forEach((url) => URL.revokeObjectURL(url));
    mediaObjectUrls = [];
    fileList.textContent = selectedMedia.length
      ? `${selectedMedia.length} из 10 выбрано`
      : "JPG, PNG, WEBP, GIF · до 64 МБ";
    if (clearMedia) clearMedia.hidden = selectedMedia.length === 0;
    if (filePreviews) {
      filePreviews.replaceChildren();
      selectedMedia.forEach((file, index) => {
        const card = document.createElement("article");
        card.className = "media-card";
        const image = document.createElement("img");
        image.className = "media-card__image";
        image.alt = file.name;
        const imageUrl = URL.createObjectURL(file);
        mediaObjectUrls.push(imageUrl);
        image.src = imageUrl;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.className = "media-card__remove";
        remove.dataset.removeMedia = String(index);
        remove.setAttribute("aria-label", `Удалить ${file.name}`);
        remove.textContent = "×";
        const footer = document.createElement("div");
        footer.className = "media-card__footer";
        const name = document.createElement("strong");
        name.textContent = file.name;
        const size = document.createElement("small");
        size.textContent = formatFileSize(file.size);
        footer.append(name, size);
        card.append(image, remove, footer);
        filePreviews.append(card);
      });
    }
    previewMedia.forEach((mediaPreview) => {
      mediaPreview.replaceChildren();
      if (selectedMedia.length) {
        const image = document.createElement("img");
        image.alt = "Предпросмотр первой фотографии";
        image.src = URL.createObjectURL(selectedMedia[0]);
        mediaObjectUrls.push(image.src);
        mediaPreview.append(image);
        if (selectedMedia.length > 1) {
          const count = document.createElement("span");
          count.className = "preview-card__count";
          count.textContent = `1 / ${selectedMedia.length}`;
          mediaPreview.append(count);
        }
      } else {
        const empty = document.createElement("span");
        empty.textContent = "Добавьте фотографии";
        mediaPreview.append(empty);
      }
    });
  };
  const setSelectedMedia = (files) => {
    selectedMedia = uniqueFiles(files);
    syncMediaInput();
    renderFiles();
  };
  mediaInput?.addEventListener("change", (event) => {
    setSelectedMedia([...selectedMedia, ...Array.from(event.target.files || [])]);
  });
  ["dragenter", "dragover"].forEach((eventName) => dropzone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.add("is-dragging");
  }));
  ["dragleave", "drop"].forEach((eventName) => dropzone?.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropzone.classList.remove("is-dragging");
  }));
  dropzone?.addEventListener("drop", (event) => {
    const files = Array.from(event.dataTransfer?.files || []).filter((file) => file.type.startsWith("image/"));
    if (!files.length || !mediaInput) return;
    setSelectedMedia([...selectedMedia, ...files]);
  });
  filePreviews?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-remove-media]");
    if (!button) return;
    const index = Number(button.dataset.removeMedia);
    setSelectedMedia(selectedMedia.filter((_file, itemIndex) => itemIndex !== index));
  });
  clearMedia?.addEventListener("click", () => setSelectedMedia([]));
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
      if (mediaInput) mediaInput.required = true;
      if (mediaLabel) mediaLabel.textContent = "Медиа";
      if (mediaGuidance) mediaGuidance.textContent = isLinkedIn
        ? "Фото будут объединены в PDF-документ"
        : "До 10 фото для карусели";
      if (postAiTask) postAiTask.value = isLinkedIn ? "instagram_to_linkedin" : "create_post";
      networkPreviews.forEach((preview) => {
        preview.hidden = preview.dataset.networkPreview !== (isLinkedIn ? "linkedin" : "instagram");
      });
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

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-use-ai-result]");
    if (!button) return;
    const generated = button.closest(".adapted")?.querySelector("[data-ai-generated]");
    if (!generated || !sourceText) return;
    sourceText.value = generated.value;
    sourceText.dispatchEvent(new Event("input", { bubbles: true }));
    if (button.closest("[data-side-panel='ai']")) {
      showPostSide("preview");
    } else {
      closeDialog(aiDialog);
      openDialog(postDialog);
    }
    sourceText.focus();
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
