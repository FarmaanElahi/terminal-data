import { useRef, useCallback } from "react";
import Editor, { type OnMount, type BeforeMount } from "@monaco-editor/react";
import type { languages, IDisposable } from "monaco-editor";
import { useAuthStore } from "@/stores/auth-store";
import type { FormulaEditorConfig } from "@/lib/api";

// ─── Language Registration (singleton) ───────────────────────────────

let langRegistered = false;
const disposables: IDisposable[] = [];

function registerFormulaLanguage(
  monaco: typeof import("monaco-editor"),
  config: FormulaEditorConfig,
) {
  if (langRegistered) return;
  langRegistered = true;

  const langId = config.languageId || "formula";

  // Register the language
  monaco.languages.register({ id: langId });

  // Monarch tokenizer from backend
  disposables.push(
    monaco.languages.setMonarchTokensProvider(
      langId,
      config.tokenizerRules as languages.IMonarchLanguage,
    ),
  );

  // Language configuration (brackets, etc.)
  disposables.push(
    monaco.languages.setLanguageConfiguration(
      langId,
      config.languageConfig as languages.LanguageConfiguration,
    ),
  );

  // Custom theme that matches our dark UI
  monaco.editor.defineTheme("formula-dark", {
    base: "vs-dark",
    inherit: true,
    rules: [
      { token: "variable", foreground: "93c5fd" }, // fields — blue
      { token: "function", foreground: "c084fc" }, // functions — purple
      { token: "keyword", foreground: "f472b6" }, // keywords — pink
      { token: "number", foreground: "34d399" }, // numbers — green
      { token: "number.float", foreground: "34d399" },
      { token: "operator.comparison", foreground: "94a3b8" },
      { token: "operator.arithmetic", foreground: "94a3b8" },
      { token: "delimiter", foreground: "64748b" },
      { token: "identifier", foreground: "fbbf24" }, // unknown — amber warning
    ],
    colors: {
      "editor.background": "#00000000", // transparent — inherits from container
      "editor.foreground": "#e2e8f0", // --foreground
      "editorCursor.foreground": "#e2e8f0",
      "editor.lineHighlightBackground": "#00000000",
      "editor.selectionBackground": "#26272d", // --muted/border
      "editorSuggestWidget.background": "#18191e", // --popover
      "editorSuggestWidget.border": "#2a2b32", // --border
      "editorSuggestWidget.foreground": "#e2e8f0",
      "editorSuggestWidget.selectedBackground": "#26272d",
      "editorSuggestWidget.highlightForeground": "#4f87ff", // --primary
    },
  });

  // Map backend kind strings to Monaco CompletionItemKind
  const kindMap: Record<string, languages.CompletionItemKind> = {
    keyword: monaco.languages.CompletionItemKind.Keyword,
    field: monaco.languages.CompletionItemKind.Variable,
    function: monaco.languages.CompletionItemKind.Function,
  };

  // Autocompletion from backend items
  disposables.push(
    monaco.languages.registerCompletionItemProvider(langId, {
      triggerCharacters: ["(", ",", " "],
      provideCompletionItems: (model, position) => {
        const word = model.getWordUntilPosition(position);
        const range = {
          startLineNumber: position.lineNumber,
          endLineNumber: position.lineNumber,
          startColumn: word.startColumn,
          endColumn: word.endColumn,
        };

        const suggestions: languages.CompletionItem[] =
          config.completionItems.map((item) => ({
            label: item.label,
            kind:
              kindMap[item.kind] || monaco.languages.CompletionItemKind.Text,
            detail: item.detail,
            documentation: item.documentation,
            insertText: item.insertText,
            insertTextRules:
              item.insertTextRules === "insertAsSnippet"
                ? monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet
                : undefined,
            range,
          }));

        return { suggestions };
      },
    }),
  );

  // Hover provider
  const hoverItems = config.completionItems.filter(
    (i) => i.documentation || i.detail,
  );
  disposables.push(
    monaco.languages.registerHoverProvider(langId, {
      provideHover: (model, position) => {
        const word = model.getWordAtPosition(position);
        if (!word) return null;
        const upper = word.word.toUpperCase();

        const item = hoverItems.find((i) => i.label.toUpperCase() === upper);
        if (!item) return null;

        return {
          range: {
            startLineNumber: position.lineNumber,
            endLineNumber: position.lineNumber,
            startColumn: word.startColumn,
            endColumn: word.endColumn,
          },
          contents: [
            { value: `**${item.label}**` },
            ...(item.detail ? [{ value: item.detail }] : []),
            ...(item.documentation ? [{ value: item.documentation }] : []),
          ],
        };
      },
    }),
  );
}

// ─── Component ───────────────────────────────────────────────────────

interface FormulaEditorProps {
  value: string;
  onChange: (value: string) => void;
  height?: number;
}

export function FormulaEditor({
  value,
  onChange,
  height = 28,
}: FormulaEditorProps) {
  const editorRef = useRef<
    import("monaco-editor").editor.IStandaloneCodeEditor | null
  >(null);
  const config = useAuthStore((s) => s.editorConfig);

  const langId = config?.languageId || "formula";

  const handleBeforeMount: BeforeMount = useCallback(
    (monaco) => {
      if (config) {
        registerFormulaLanguage(monaco, config);
      }
    },
    [config],
  );

  const handleMount: OnMount = useCallback((editor) => {
    editorRef.current = editor;

    // Single-line mode: Enter accepts suggestion or triggers suggest
    editor.addCommand(3 /* KeyCode.Enter */, () => {
      const suggestWidget = editor.getContribution(
        "editor.contrib.suggestController",
      ) as { model?: { state?: number } } | null;
      if (suggestWidget?.model?.state === 2) {
        editor.trigger("keyboard", "acceptSelectedSuggestion", {});
      } else {
        editor.trigger("keyboard", "editor.action.triggerSuggest", {});
      }
    });
  }, []);

  const handleChange = useCallback(
    (val: string | undefined) => {
      onChange(val ?? "");
    },
    [onChange],
  );

  // Fallback while config hasn't loaded (shouldn't happen since it loads on boot)
  if (!config) {
    return (
      <div
        className="border border-border rounded-sm bg-background px-2 flex items-center text-xs text-muted-foreground font-mono"
        style={{ height: `${height}px` }}
      >
        {value || "…"}
      </div>
    );
  }

  return (
    <div
      className="border border-border rounded-sm overflow-visible bg-background relative pr-2"
      style={{ height: `${height}px` }}
    >
      <Editor
        height={height}
        language={langId}
        value={value}
        onChange={handleChange}
        beforeMount={handleBeforeMount}
        onMount={handleMount}
        theme="formula-dark"
        options={{
          lineNumbers: "off",
          glyphMargin: false,
          folding: false,
          lineDecorationsWidth: 8,
          lineNumbersMinChars: 0,
          minimap: { enabled: false },
          scrollbar: { horizontal: "auto", vertical: "auto" },
          wordWrap: "on",
          overviewRulerLanes: 0,
          renderLineHighlight: "none",
          hideCursorInOverviewRuler: true,
          contextmenu: false,
          fontSize: 12,
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          suggestOnTriggerCharacters: true,
          quickSuggestions: true,
          wordBasedSuggestions: "off",
          fixedOverflowWidgets: true, // Allow widgets to overflow container bounds
          padding: { top: 8, bottom: 8 },
          scrollBeyondLastLine: false,
          automaticLayout: true,
        }}
      />
    </div>
  );
}
