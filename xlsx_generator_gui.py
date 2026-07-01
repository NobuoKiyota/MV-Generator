import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import threading
from dotenv import load_dotenv
from utils import analyze_audio, generate_initial_timeline, parse_tagged_lyrics, export_project_xlsx

# 環境変数の読み込み
load_dotenv()

class XlsxGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("📊 Song Prompt Excel Generator (MIDI-Sync)")
        self.root.geometry("600x740")  # MIDI欄追加のため高さを少し広げる
        self.root.resizable(False, False)
        
        # 変数定義
        self.audio_path = tk.StringVar(value="")
        self.midi_path = tk.StringVar(value="")
        self.audio_type = tk.StringVar(value="vocal")
        self.bpm_val = tk.StringVar(value="")
        self.offset_val = tk.DoubleVar(value=0.0)
        self.time_sig = tk.StringVar(value="4/4")
        self.vis_style = tk.StringVar(value="特になし")
        self.aspect_ratio = tk.StringVar(value="16:9")
        self.api_key = tk.StringVar(value=os.environ.get("GEMINI_API_KEY", ""))
        
        self.create_widgets()
        self.toggle_lyrics_state()

    def create_widgets(self):
        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 列の比率設定
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        # 1. 音源ファイル選択
        lbl_audio = ttk.Label(main_frame, text=" BGM Audio File:", font=("Meiryo UI", 9, "bold"))
        lbl_audio.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        
        audio_entry_frame = ttk.Frame(main_frame)
        audio_entry_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        
        self.entry_audio = ttk.Entry(audio_entry_frame, textvariable=self.audio_path)
        self.entry_audio.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        btn_browse = ttk.Button(audio_entry_frame, text="Browse...", command=self.browse_audio)
        btn_browse.pack(side=tk.RIGHT)

        # [NEW] 1.5. MIDIファイル選択 (Optional)
        lbl_midi = ttk.Label(main_frame, text=" Melody/Marker MIDI File (.mid) (Highly Recommended):", font=("Meiryo UI", 9, "bold"), foreground="green")
        lbl_midi.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        
        midi_entry_frame = ttk.Frame(main_frame)
        midi_entry_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        
        self.entry_midi = ttk.Entry(midi_entry_frame, textvariable=self.midi_path)
        self.entry_midi.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        btn_browse_midi = ttk.Button(midi_entry_frame, text="Browse...", command=self.browse_midi)
        btn_browse_midi.pack(side=tk.RIGHT)

        # 2. 音源のタイプ (Radio buttons)
        lbl_type = ttk.Label(main_frame, text=" Song Type:", font=("Meiryo UI", 9, "bold"))
        lbl_type.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        
        type_frame = ttk.Frame(main_frame)
        type_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
        
        rb_vocal = ttk.Radiobutton(type_frame, text="歌詞もの (Vocal)", variable=self.audio_type, value="vocal", command=self.toggle_lyrics_state)
        rb_vocal.pack(side=tk.LEFT, padx=(0, 20))
        
        rb_inst = ttk.Radiobutton(type_frame, text="インスト (Instrumental)", variable=self.audio_type, value="inst", command=self.toggle_lyrics_state)
        rb_inst.pack(side=tk.LEFT)

        # 3. 歌詞情報入力
        self.lbl_lyrics = ttk.Label(main_frame, text=" Lyrics (with Section Tags):", font=("Meiryo UI", 9, "bold"))
        self.lbl_lyrics.grid(row=6, column=0, columnspan=2, sticky=tk.W, pady=(0, 2))
        
        lyrics_frame = ttk.Frame(main_frame)
        lyrics_frame.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=(0, 8))
        
        self.txt_lyrics = tk.Text(lyrics_frame, height=8, width=70, font=("Meiryo UI", 9))
        self.txt_lyrics.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(lyrics_frame, command=self.txt_lyrics.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_lyrics.config(yscrollcommand=scrollbar.set)
        
        # 4. BPMと1小節目開始時間 (オフセット)
        param_frame = ttk.Frame(main_frame)
        param_frame.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        
        lbl_bpm = ttk.Label(param_frame, text="BPM (Bypassed if empty):", font=("Meiryo UI", 9))
        lbl_bpm.pack(side=tk.LEFT, padx=(0, 5))
        self.entry_bpm = ttk.Entry(param_frame, textvariable=self.bpm_val, width=12)
        self.entry_bpm.pack(side=tk.LEFT, padx=(0, 30))
        
        lbl_offset = ttk.Label(param_frame, text="First Bar Start Time (sec):", font=("Meiryo UI", 9))
        lbl_offset.pack(side=tk.LEFT, padx=(0, 5))
        self.entry_offset = ttk.Entry(param_frame, textvariable=self.offset_val, width=10)
        self.entry_offset.pack(side=tk.LEFT)

        # 5. 詳細設定 (Advanced Settings Frame)
        self.advanced_frame = ttk.LabelFrame(main_frame, text=" Advanced Settings (Optional) ", padding="10")
        self.advanced_frame.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        
        # 拍子
        lbl_sig = ttk.Label(self.advanced_frame, text="Time Signature:")
        lbl_sig.grid(row=0, column=0, sticky=tk.W, padx=(0, 5), pady=5)
        cb_sig = ttk.Combobox(self.advanced_frame, textvariable=self.time_sig, values=["4/4", "3/4", "6/8", "2/4"], width=10, state="readonly")
        cb_sig.grid(row=0, column=1, sticky=tk.W, padx=(0, 20), pady=5)
        
        # スタイルと比率
        lbl_style = ttk.Label(self.advanced_frame, text="Visual Style:")
        lbl_style.grid(row=0, column=2, sticky=tk.W, padx=(0, 5), pady=5)
        cb_style = ttk.Combobox(self.advanced_frame, textvariable=self.vis_style, values=["特になし", "シネマティック (Cinematic)", "アニメ風 (Anime style)", "サイバーパンク (Cyberpunk)", "水彩画風 (Watercolor)", "3D CG", "ピクセルアート (Pixel art)"], width=18, state="readonly")
        cb_style.grid(row=0, column=3, sticky=tk.W, pady=5)
        
        lbl_ratio = ttk.Label(self.advanced_frame, text="Aspect Ratio:")
        lbl_ratio.grid(row=1, column=0, sticky=tk.W, padx=(0, 5), pady=5)
        cb_ratio = ttk.Combobox(self.advanced_frame, textvariable=self.aspect_ratio, values=["16:9", "9:16", "1:1"], width=10, state="readonly")
        cb_ratio.grid(row=1, column=1, sticky=tk.W, pady=5)

        # 6. API Key とステータス表示
        api_frame = ttk.Frame(main_frame)
        api_frame.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        
        lbl_api = ttk.Label(api_frame, text="Gemini API Key (Optional):", font=("Meiryo UI", 9))
        lbl_api.pack(side=tk.LEFT, padx=(0, 5))
        self.entry_api = ttk.Entry(api_frame, textvariable=self.api_key, show="*", width=30)
        self.entry_api.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ステータス・プログレスラベル
        self.lbl_status = ttk.Label(main_frame, text="Ready", font=("Meiryo UI", 9, "italic"), foreground="gray")
        self.lbl_status.grid(row=11, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))

        # 7. 実行ボタン
        self.btn_generate = ttk.Button(main_frame, text="🎵 Generate Excel (.xlsx) & Save", command=self.start_generation_thread)
        self.btn_generate.grid(row=12, column=0, columnspan=2, sticky="ew", ipady=5)

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

    def start_generation_thread(self):
        # 簡易チェック
        api = self.api_key.get().strip()
        if not api:
            messagebox.showerror("Error", "Gemini API Key is not configured. Please input in the text box or configure in .env.")
            return
            
        # ボタンの無効化
        self.btn_generate.config(state="disabled")
        self.set_status("Starting process...", "blue")
        
        # 別スレッドで実行してフリーズを防ぐ
        thread = threading.Thread(target=self.generate_excel_process, daemon=True)
        thread.start()

    def generate_excel_process(self):
        try:
            audio = self.audio_path.get().strip()
            midi = self.midi_path.get().strip()
            is_vocal = self.audio_type.get() == "vocal"
            lyrics_text = self.txt_lyrics.get("1.0", tk.END).strip() if is_vocal else ""
            
            bpm = 120.0
            duration = 180.0
            
            # 1. 音響解析
            if audio:
                if not os.path.exists(audio):
                    self.root.after(0, lambda: messagebox.showerror("Error", f"Audio file not found:\n{audio}"))
                    self.root.after(0, lambda: self.btn_generate.config(state="normal"))
                    self.root.after(0, lambda: self.set_status("Ready", "gray"))
                    return
                    
                self.root.after(0, lambda: self.set_status("Analyzing BGM tempo & duration (Librosa)...", "blue"))
                analysis = analyze_audio(audio)
                if analysis:
                    duration = analysis["duration"]
                    # BPM指定がなければ自動検出を使用
                    user_bpm = self.bpm_val.get().strip()
                    if not user_bpm:
                        bpm = analysis["bpm"]
                    else:
                        try:
                            bpm = float(user_bpm)
                        except ValueError:
                            bpm = analysis["bpm"]
                else:
                    self.root.after(0, lambda: messagebox.showwarning("Warning", "Audio analysis failed. Using defaults (BPM=120, duration=180)."))
            else:
                user_bpm = self.bpm_val.get().strip()
                if user_bpm:
                    try:
                        bpm = float(user_bpm)
                    except ValueError:
                        pass
                self.root.after(0, lambda: self.set_status("No audio file. Using default duration (180s) and BPM.", "orange"))

            # MIDIファイルの存在確認
            if midi and not os.path.exists(midi):
                self.root.after(0, lambda: messagebox.showerror("Error", f"MIDI file not found:\n{midi}"))
                self.root.after(0, lambda: self.btn_generate.config(state="normal"))
                self.root.after(0, lambda: self.set_status("Ready", "gray"))
                return

            # 2. Gemini タイムライン生成
            self.root.after(0, lambda: self.set_status("Aligning MIDI with lyrics & generating prompts with Gemini...", "blue"))
            
            timeline_result = generate_initial_timeline(
                lyrics=lyrics_text,
                bpm=bpm,
                duration=duration,
                core_concept="",
                global_rules="",
                section_rules="",
                keywords="",
                api_key=self.api_key.get().strip(),
                first_bar_offset=self.offset_val.get(),
                time_signature=self.time_sig.get(),
                split_unit="セクションごと",
                visual_style=self.vis_style.get(),
                aspect_ratio=self.aspect_ratio.get(),
                audio_path=audio,
                midi_path=midi
            )
            
            if not timeline_result or "timeline" not in timeline_result:
                self.root.after(0, lambda: messagebox.showerror("Error", "Failed to generate timeline from Gemini (Invalid response)."))
                self.root.after(0, lambda: self.btn_generate.config(state="normal"))
                self.root.after(0, lambda: self.set_status("Ready", "gray"))
                return
                
            timeline_data = timeline_result["timeline"]
            summary = timeline_result.get("summary", {})
            result_bpm = timeline_result.get("bpm", bpm)
            project_title = summary.get("title", "my_song_project")
            
            # 3. Excel 保存先の決定ダイアログ
            self.root.after(0, lambda: self.set_status("Choosing save path...", "blue"))
            
            # 保存先ファイルパスの決定
            default_filename = f"{project_title}_timeline.xlsx"
            save_path = filedialog.asksaveasfilename(
                initialfile=default_filename,
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            
            if not save_path:
                self.root.after(0, lambda: self.set_status("Save canceled.", "orange"))
                self.root.after(0, lambda: self.btn_generate.config(state="normal"))
                return

            # 4. Excel の書き出し
            self.root.after(0, lambda: self.set_status("Writing Excel file...", "blue"))
            
            # Excel バイナリの構築
            core_concept_text = ""
            global_rules_text = ""
            if summary:
                core_concept_text = f"【世界観・コンセプト】\n{summary.get('concept', '')}\n\n【キャラクター設定】\n{summary.get('characters', '')}"
                global_rules_text = summary.get('rules', '')

            xlsx_bytes = export_project_xlsx(
                project_name=project_title,
                timeline_data=timeline_data,
                bpm=result_bpm,
                duration=duration,
                core_concept=core_concept_text,
                global_rules=global_rules_text,
                first_bar_offset=self.offset_val.get(),
                time_signature=self.time_sig.get(),
                split_unit="MIDI同期",
                visual_style=self.vis_style.get(),
                aspect_ratio=self.aspect_ratio.get()
            )
            
            # 保存処理
            with open(save_path, "wb") as f:
                f.write(xlsx_bytes)
                
            self.root.after(0, lambda: self.set_status("Process completed successfully!", "green"))
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Excel file successfully generated and saved at:\n{save_path}"))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Error", f"An unexpected error occurred:\n{e}"))
            self.root.after(0, lambda: self.set_status("Error occurred.", "red"))
        finally:
            self.root.after(0, lambda: self.btn_generate.config(state="normal"))

if __name__ == "__main__":
    root = tk.Tk()
    app = XlsxGeneratorApp(root)
    root.mainloop()
