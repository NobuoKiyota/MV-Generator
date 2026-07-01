import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import threading
from dotenv import load_dotenv
from utils import (
    analyze_audio, 
    generate_concept_settings, 
    generate_timeline_from_concept, 
    export_project_xlsx
)

# 環境変数の読み込み
load_dotenv()

class XlsxGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📊 Song MV Concept & Timeline Generator")
        self.root.geometry("620x780")
        
        # 共通変数
        self.audio_path = tk.StringVar(value="")
        self.midi_path = tk.StringVar(value="")
        self.audio_type = tk.StringVar(value="vocal")
        self.raw_idea = tk.StringVar(value="")
        
        self.bpm_val = tk.StringVar(value="")
        self.offset_val = tk.DoubleVar(value=0.0)
        self.time_sig = tk.StringVar(value="4/4")
        self.vis_style = tk.StringVar(value="特になし")
        self.aspect_ratio = tk.StringVar(value="16:9")
        self.api_key = tk.StringVar(value=os.environ.get("GEMINI_API_KEY", ""))
        
        # フェーズ1での出力値（フェーズ2への入力）
        self.concept_title = tk.StringVar(value="")
        
        self.create_widgets()
        self.toggle_lyrics_state()

    def create_widgets(self):
        # 1. 最下部共通：APIキーとステータス表示用フレーム
        bottom_frame = ttk.Frame(self.root, padding="10")
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        lbl_api = ttk.Label(bottom_frame, text="Gemini API Key (Required):", font=("Meiryo UI", 9, "bold"))
        lbl_api.pack(side=tk.LEFT, padx=(0, 5))
        self.entry_api = ttk.Entry(bottom_frame, textvariable=self.api_key, show="*", width=30)
        self.entry_api.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.lbl_status = ttk.Label(bottom_frame, text="Ready", font=("Meiryo UI", 9, "italic"), foreground="gray")
        self.lbl_status.pack(side=tk.RIGHT)

        # 2. タブコントロールの作成
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # 各タブフレーム
        self.tab_concept = ttk.Frame(self.notebook, padding="15")
        self.tab_timeline = ttk.Frame(self.notebook, padding="15")
        
        self.notebook.add(self.tab_concept, text="🎨 1. コンセプト・キャラクター設定")
        self.notebook.add(self.tab_timeline, text="📊 2. 演出コンテ (Excel) 生成")

        # ----------------------------------------------------
        # 🎨 タブ1: コンセプト設計設定 UI の構築
        # ----------------------------------------------------
        self.tab_concept.columnconfigure(0, weight=1)
        self.tab_concept.columnconfigure(1, weight=1)
        
        # 音源ファイル選択
        lbl_audio = ttk.Label(self.tab_concept, text=" BGM Audio File:", font=("Meiryo UI", 9, "bold"))
        lbl_audio.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        
        audio_frame = ttk.Frame(self.tab_concept)
        audio_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.entry_audio = ttk.Entry(audio_frame, textvariable=self.audio_path)
        self.entry_audio.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        btn_browse = ttk.Button(audio_frame, text="Browse...", command=self.browse_audio)
        btn_browse.pack(side=tk.RIGHT)
        
        # MIDIファイル選択
        lbl_midi = ttk.Label(self.tab_concept, text=" Melody/Marker MIDI File (.mid) (Highly Recommended):", font=("Meiryo UI", 9, "bold"), foreground="green")
        lbl_midi.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        
        midi_frame = ttk.Frame(self.tab_concept)
        midi_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.entry_midi = ttk.Entry(midi_frame, textvariable=self.midi_path)
        self.entry_midi.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        btn_browse_midi = ttk.Button(midi_frame, text="Browse...", command=self.browse_midi)
        btn_browse_midi.pack(side=tk.RIGHT)
        
        # 歌詞タイプ選択
        lbl_type = ttk.Label(self.tab_concept, text=" Song Type:", font=("Meiryo UI", 9, "bold"))
        lbl_type.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        
        type_frame = ttk.Frame(self.tab_concept)
        type_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        rb_vocal = ttk.Radiobutton(type_frame, text="歌詞もの (Vocal)", variable=self.audio_type, value="vocal", command=self.toggle_lyrics_state)
        rb_vocal.pack(side=tk.LEFT, padx=(0, 20))
        rb_inst = ttk.Radiobutton(type_frame, text="インスト (Instrumental)", variable=self.audio_type, value="inst", command=self.toggle_lyrics_state)
        rb_inst.pack(side=tk.LEFT)
        
        # 歌詞入力
        self.lbl_lyrics = ttk.Label(self.tab_concept, text=" Lyrics (with Section Tags):", font=("Meiryo UI", 9, "bold"))
        self.lbl_lyrics.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        
        lyrics_txt_frame = ttk.Frame(self.tab_concept)
        lyrics_txt_frame.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
        self.txt_lyrics = tk.Text(lyrics_txt_frame, height=6, width=70, font=("Meiryo UI", 9))
        self.txt_lyrics.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(lyrics_txt_frame, command=self.txt_lyrics.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_lyrics.config(yscrollcommand=scrollbar.set)
        
        # ユーザーのラフ要望イメージ入力
        lbl_idea = ttk.Label(self.tab_concept, text=" Visual Direction/Rough Idea:", font=("Meiryo UI", 9, "bold"))
        lbl_idea.grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        self.entry_idea = ttk.Entry(self.tab_concept, textvariable=self.raw_idea)
        self.entry_idea.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        # コンセプト生成ボタン
        self.btn_gen_concept = ttk.Button(self.tab_concept, text="🎨 STEP 1: ビジュアル設定（世界観・キャラ）をAI自動生成", command=self.start_concept_thread)
        self.btn_gen_concept.grid(row=10, column=0, columnspan=2, sticky="ew", ipady=4, pady=(0, 15))

        # 設定出力・手動修正エリア
        lbl_result_frame = ttk.LabelFrame(self.tab_concept, text=" 📝 AI提案設定図 (人間が直接修正して決定できます) ", padding="10")
        lbl_result_frame.grid(row=11, column=0, columnspan=2, sticky="nsew")
        lbl_result_frame.columnconfigure(0, weight=1)
        lbl_result_frame.columnconfigure(1, weight=1)
        
        # 提案タイトル
        lbl_res_title = ttk.Label(lbl_result_frame, text="Proposed Project Title:")
        lbl_res_title.grid(row=0, column=0, sticky=tk.W)
        self.entry_res_title = ttk.Entry(lbl_result_frame, textvariable=self.concept_title)
        self.entry_res_title.grid(row=0, column=1, sticky="ew", pady=2)
        
        # 世界観コンセプト設定
        lbl_res_concept = ttk.Label(lbl_result_frame, text="Worldview & Concept:")
        lbl_res_concept.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.txt_res_concept = tk.Text(lbl_result_frame, height=3, width=70, font=("Meiryo UI", 9))
        self.txt_res_concept.grid(row=2, column=0, columnspan=2, sticky="ew", pady=2)
        
        # キャラクタービジュアル設定
        lbl_res_char = ttk.Label(lbl_result_frame, text="Character Design Details (Hair, Eyes, Clothes):")
        lbl_res_char.grid(row=3, column=0, sticky=tk.W, pady=(5, 0))
        self.txt_res_char = tk.Text(lbl_result_frame, height=3, width=70, font=("Meiryo UI", 9))
        self.txt_res_char.grid(row=4, column=0, columnspan=2, sticky="ew", pady=2)
        
        # 色彩・トーン共通ルール
        lbl_res_rules = ttk.Label(lbl_result_frame, text="Color Palette & Video Tone Rules:")
        lbl_res_rules.grid(row=5, column=0, sticky=tk.W, pady=(5, 0))
        self.txt_res_rules = tk.Text(lbl_result_frame, height=3, width=70, font=("Meiryo UI", 9))
        self.txt_res_rules.grid(row=6, column=0, columnspan=2, sticky="ew", pady=2)

        # ----------------------------------------------------
        # 📊 タブ2: タイムライン（Excel）生成 UI の構築
        # ----------------------------------------------------
        self.tab_timeline.columnconfigure(0, weight=1)
        self.tab_timeline.columnconfigure(1, weight=1)
        
        lbl_timeline_header = ttk.Label(self.tab_timeline, text="📊 決定された世界観設定を各カットに引き当ててタイムラインを作成します", font=("Meiryo UI", 10, "bold"))
        lbl_timeline_header.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 15))
        
        # BPM・オフセットの設定
        lbl_music = ttk.LabelFrame(self.tab_timeline, text=" Music Parameters (BPM / Offset) ", padding="10")
        lbl_music.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        
        lbl_bpm = ttk.Label(lbl_music, text="BPM (Empty for Auto-Detect):")
        lbl_bpm.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.entry_bpm = ttk.Entry(lbl_music, textvariable=self.bpm_val, width=15)
        self.entry_bpm.grid(row=0, column=1, sticky=tk.W, padx=15, pady=5)
        
        lbl_offset = ttk.Label(lbl_music, text="First Bar Start Time (sec):")
        lbl_offset.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.entry_offset = ttk.Entry(lbl_music, textvariable=self.offset_val, width=15)
        self.entry_offset.grid(row=0, column=3, sticky=tk.W, pady=5)
        
        # その他の詳細設定
        lbl_gen_opt = ttk.LabelFrame(self.tab_timeline, text=" Generation Options ", padding="10")
        lbl_gen_opt.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        
        lbl_sig = ttk.Label(lbl_gen_opt, text="Time Signature:")
        lbl_sig.grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        cb_sig = ttk.Combobox(lbl_gen_opt, textvariable=self.time_sig, values=["4/4", "3/4", "6/8", "2/4"], width=12, state="readonly")
        cb_sig.grid(row=0, column=1, sticky=tk.W, padx=15, pady=5)
        
        lbl_style = ttk.Label(lbl_gen_opt, text="Visual Style:")
        lbl_style.grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        cb_style = ttk.Combobox(lbl_gen_opt, textvariable=self.vis_style, values=["特になし", "シネマティック (Cinematic)", "アニメ風 (Anime style)", "サイバーパンク (Cyberpunk)", "水彩画風 (Watercolor)", "3D CG", "ピクセルアート (Pixel art)"], width=18, state="readonly")
        cb_style.grid(row=0, column=3, sticky=tk.W, pady=5)
        
        lbl_ratio = ttk.Label(lbl_gen_opt, text="Aspect Ratio:")
        lbl_ratio.grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        cb_ratio = ttk.Combobox(lbl_gen_opt, textvariable=self.aspect_ratio, values=["16:9", "9:16", "1:1"], width=12, state="readonly")
        cb_ratio.grid(row=1, column=1, sticky=tk.W, pady=5)

        # タイムライン生成実行ボタン
        self.btn_gen_timeline = ttk.Button(self.tab_timeline, text="🎵 STEP 2: 世界観が統一されたタイムラインを構築し、Excel (.xlsx) を保存", command=self.start_timeline_thread)
        self.btn_gen_timeline.grid(row=3, column=0, columnspan=2, sticky="ew", ipady=6, pady=10)
        
        # ガイドメッセージ
        lbl_guide = ttk.Label(self.tab_timeline, text="※まずタブ1でコンセプト設定を作成・編集してから、このボタンを押してください。\nタブ1で確定されたキャラクタービジュアルやカラーパレットがすべてのカットプロンプトへ自動流し込みされます。", font=("Meiryo UI", 9, "italic"), justify=tk.LEFT)
        lbl_guide.grid(row=4, column=0, columnspan=2, sticky=tk.W)

    def browse_audio(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Audio files", "*.mp3 *.wav *.m4a *.ogg"), ("All files", "*.*")]
        )
        if filepath:
            self.audio_path.set(filepath)

    def browse_midi(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("MIDI files", "*.mid *.midi"), ("All files", "*.*")]
        )
        if filepath:
            self.midi_path.set(filepath)

    def toggle_lyrics_state(self):
        if self.audio_type.get() == "vocal":
            self.txt_lyrics.config(state="normal", background="white")
            self.lbl_lyrics.config(foreground="black")
        else:
            self.txt_lyrics.config(state="disabled", background="#F0F0F0")
            self.lbl_lyrics.config(foreground="gray")

    def set_status(self, text, color="gray"):
        self.lbl_status.config(text=text, foreground=color)
        self.root.update_idletasks()

    # =====================================================================
    # 🎨 スレッド制御: ステップ1 コンセプト案生成
    # =====================================================================
    def start_concept_thread(self):
        api = self.api_key.get().strip()
        if not api:
            messagebox.showerror("Error", "Gemini API Key is required.")
            return
            
        self.btn_gen_concept.config(state="disabled")
        self.set_status("Analyzing audio & generating concept settings...", "blue")
        
        thread = threading.Thread(target=self.generate_concept_process, daemon=True)
        thread.start()

    def generate_concept_process(self):
        try:
            audio = self.audio_path.get().strip()
            is_vocal = self.audio_type.get() == "vocal"
            lyrics_text = self.txt_lyrics.get("1.0", tk.END).strip() if is_vocal else ""
            idea = self.raw_idea.get().strip()
            
            bpm = 120.0
            duration = 180.0
            
            # 音源解析
            if audio:
                if not os.path.exists(audio):
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Audio file not found: {audio}"))
                    return
                self.root.after(0, lambda: self.set_status("Analyzing BGM duration & BPM...", "blue"))
                analysis = analyze_audio(audio)
                if analysis:
                    duration = analysis["duration"]
                    bpm = analysis["bpm"]
                    # BPM入力欄に自動検出値を反映
                    self.root.after(0, lambda: self.bpm_val.set(str(bpm)))
            
            # コンセプト提案生成
            self.root.after(0, lambda: self.set_status("Asking Gemini for visual setup ideas...", "blue"))
            concept = generate_concept_settings(
                lyrics=lyrics_text,
                bpm=bpm,
                duration=duration,
                raw_idea=idea,
                api_key=self.api_key.get().strip(),
                audio_path=audio
            )
            
            if not concept:
                self.root.after(0, lambda: messagebox.showerror("Error", "Failed to generate concept. Check your network or API Key."))
                return
                
            # 出力テキストをUIにセット
            self.root.after(0, lambda: self.concept_title.set(concept.get("title", "")))
            
            # テキストエリアへの書き込み
            self.root.after(0, lambda: self.txt_res_concept.delete("1.0", tk.END))
            self.root.after(0, lambda: self.txt_res_concept.insert("1.0", concept.get("concept", "")))
            
            self.root.after(0, lambda: self.txt_res_char.delete("1.0", tk.END))
            self.root.after(0, lambda: self.txt_res_char.insert("1.0", concept.get("characters", "")))
            
            self.root.after(0, lambda: self.txt_res_rules.delete("1.0", tk.END))
            self.root.after(0, lambda: self.txt_res_rules.insert("1.0", concept.get("rules", "")))
            
            self.root.after(0, lambda: self.set_status("Concept settings generated successfully!", "green"))
            self.root.after(0, lambda: messagebox.showinfo("Success", "Concept generated! Please review/edit the settings, then switch to Tab 2 to create the timeline."))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error in concept generation:\n{e}"))
            self.root.after(0, lambda: self.set_status("Error occurred.", "red"))
        finally:
            self.root.after(0, lambda: self.btn_gen_concept.config(state="normal"))

    # =====================================================================
    # 📊 スレッド制御: ステップ2 タイムライン & Excel 保存
    # =====================================================================
    def start_timeline_thread(self):
        # コンセプト設定が入力されているかチェック
        title = self.concept_title.get().strip()
        concept = self.txt_res_concept.get("1.0", tk.END).strip()
        
        if not title or not concept:
            messagebox.showerror("Error", "Please complete STEP 1 (Concept Generation) in Tab 1 first.")
            return
            
        self.btn_gen_timeline.config(state="disabled")
        self.set_status("Generating consistent timeline...", "blue")
        
        thread = threading.Thread(target=self.generate_timeline_process, daemon=True)
        thread.start()

    def generate_timeline_process(self):
        try:
            audio = self.audio_path.get().strip()
            midi = self.midi_path.get().strip()
            is_vocal = self.audio_type.get() == "vocal"
            lyrics_text = self.txt_lyrics.get("1.0", tk.END).strip() if is_vocal else ""
            
            # タブ1で確定されたビジュアル設定をロード
            concept_summary = {
                "title": self.concept_title.get().strip(),
                "concept": self.txt_res_concept.get("1.0", tk.END).strip(),
                "characters": self.txt_res_char.get("1.0", tk.END).strip(),
                "rules": self.txt_res_rules.get("1.0", tk.END).strip()
            }
            
            # 音楽パラメータの読み込み
            bpm = 120.0
            duration = 180.0
            
            # 音響の事前解析
            if audio:
                analysis = analyze_audio(audio)
                if analysis:
                    duration = analysis["duration"]
                    user_bpm = self.bpm_val.get().strip()
                    if not user_bpm:
                        bpm = analysis["bpm"]
                    else:
                        try:
                            bpm = float(user_bpm)
                        except ValueError:
                            bpm = analysis["bpm"]
            else:
                user_bpm = self.bpm_val.get().strip()
                if user_bpm:
                    try:
                        bpm = float(user_bpm)
                    except ValueError:
                        pass
                        
            # MIDIの存在確認
            if midi and not os.path.exists(midi):
                self.root.after(0, lambda: messagebox.showerror("Error", f"MIDI file not found: {midi}"))
                return

            # タイムライン展開の実行
            self.root.after(0, lambda: self.set_status("Applying concept to each timeline slot...", "blue"))
            timeline_result = generate_timeline_from_concept(
                lyrics=lyrics_text,
                bpm=bpm,
                duration=duration,
                concept_summary=concept_summary,
                api_key=self.api_key.get().strip(),
                first_bar_offset=self.offset_val.get(),
                time_signature=self.time_sig.get(),
                visual_style=self.vis_style.get(),
                aspect_ratio=self.aspect_ratio.get(),
                audio_path=audio,
                midi_path=midi
            )
            
            if not timeline_result or "timeline" not in timeline_result:
                self.root.after(0, lambda: messagebox.showerror("Error", "Timeline generation failed. Please check logs."))
                return

            timeline_data = timeline_result["timeline"]
            
            # Excel保存先の決定ダイアログ
            self.root.after(0, lambda: self.set_status("Selecting save path...", "blue"))
            default_filename = f"{concept_summary['title']}_timeline.xlsx"
            save_path = filedialog.asksaveasfilename(
                initialfile=default_filename,
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            
            if not save_path:
                self.root.after(0, lambda: self.set_status("Excel save canceled.", "orange"))
                return

            # Excel エクスポート
            self.root.after(0, lambda: self.set_status("Writing styled Excel file...", "blue"))
            
            xlsx_bytes = export_project_xlsx(
                project_name=concept_summary['title'],
                timeline_data=timeline_data,
                bpm=timeline_result.get("bpm", bpm),
                duration=duration,
                core_concept=f"【世界観・コンセプト】\n{concept_summary['concept']}\n\n【キャラクター設定】\n{concept_summary['characters']}",
                global_rules=concept_summary['rules'],
                first_bar_offset=self.offset_val.get(),
                time_signature=self.time_sig.get(),
                split_unit="MIDI同期" if midi else "セクション分割",
                visual_style=self.vis_style.get(),
                aspect_ratio=self.aspect_ratio.get()
            )
            
            with open(save_path, "wb") as f:
                f.write(xlsx_bytes)
                
            self.root.after(0, lambda: self.set_status("Excel generated and saved!", "green"))
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Worldview-aligned Excel sheet successfully saved at:\n{save_path}"))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error in timeline generation:\n{e}"))
            self.root.after(0, lambda: self.set_status("Error occurred.", "red"))
        finally:
            self.root.after(0, lambda: self.btn_gen_timeline.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = XlsxGeneratorApp(root)
    root.mainloop()
