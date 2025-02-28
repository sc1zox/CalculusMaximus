import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import pdfplumber
import re
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from collections import Counter


class Course:
    def __init__(self, bereich, kurs, note, ects):
        self.bereich = bereich
        self.kurs = kurs
        self.note = note
        self.ects = ects

    def __repr__(self):
        return f"Course(bereich='{self.bereich}', kurs='{self.kurs}', note='{self.note}', ects={self.ects})"


class PDFParserApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WIAI Datasheet extractor and calculator")
        self.root.geometry("1650x1050")

        self.frame_left = tk.Frame(root)
        self.frame_left.pack(side="left", expand=True, fill="both", padx=10, pady=10)

        self.frame_right = tk.Frame(root, width=400, relief="solid", borderwidth=2)
        self.frame_right.pack(side="right", fill="y", padx=10, pady=10)

        self.btn_open = tk.Button(self.frame_left, text="PDF öffnen", command=self.load_pdf, font=("Arial", 12))
        self.btn_open.pack(pady=10)

        self.tree = ttk.Treeview(self.frame_left, columns=("Bereich", "Kurs", "Note", "ECTS"), show="headings")
        self.tree.heading("Bereich", text="Bereich")
        self.tree.heading("Kurs", text="Kurs")
        self.tree.heading("Note", text="Note")
        self.tree.heading("ECTS", text="ECTS")
        self.tree.pack(expand=True, fill="both", padx=10, pady=10)

        self.tree.column("Bereich", anchor="center", stretch=True)
        self.tree.column("Note", anchor="center", stretch=True)
        self.tree.column("ECTS", anchor="center", stretch=True)

        self.ects_label = tk.Label(self.frame_left, text="Gesamte ECTS-Summe: 0.0 | Durchschnitt: 0.0",
                                   font=("Arial", 12, "bold"))
        self.ects_label.pack(pady=5)

        self.prognose_label = tk.Label(self.frame_right, text="Notenprognose (verbleibende ECTS)",
                                       font=("Arial", 14, "bold"))
        self.prognose_label.pack(pady=10)

        self.prognose_text = tk.Text(self.frame_right, height=15, width=50, font=("Arial", 12))
        self.prognose_text.pack(padx=10, pady=10)

        self.graph_frame = tk.Frame(self.frame_right)
        self.graph_frame.pack(fill="both", expand=True, padx=10, pady=10)

    def load_pdf(self):
        file_path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if not file_path:
            return

        try:
            data, ects_sum, avg_grade, ects_sum_calc = self.extract_data(file_path)

            for row in self.tree.get_children():
                self.tree.delete(row)

            for course in data:
                item_id = self.tree.insert("", "end", values=(course.bereich, course.kurs, course.note, course.ects))

                if course.bereich == "A5":
                    self.tree.item(item_id, tags=("red",))

            self.tree.tag_configure("red", background="red", foreground="white")

            self.ects_label.config(text=f"Gesamte ECTS-Summe: {ects_sum:.1f} | Durchschnitt: {avg_grade:.3f}")

            self.calculate_prognosis(ects_sum, avg_grade, ects_sum_calc)
            self.plot_grade_distribution(data)

        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler beim Verarbeiten der PDF:\n{e}")

    def extract_data(self, file_path):
        data = []
        ects_sum = 0
        ects_sum_calc = 0
        grades_weighted_sum = 0
        current_section = None

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                words = page.extract_words()
                lines = pdfplumber.utils.cluster_objects(words, lambda w: w["top"], 2)
                section_pattern = re.compile(r"(A\d|B\d) .*")

                for line in lines:
                    text_line = " ".join(w["text"] for w in line).strip()
                    if re.match(r"^(WS|SS)\d{2}", text_line):
                        continue

                    section_match = section_pattern.match(text_line)
                    if section_match:
                        current_section = section_match.group(1)
                        continue

                    match = re.search(r'^(.*?)(\s+\d,\d\s+\d,\d)', text_line)
                    if match and current_section:
                        kurs = match.group(1).strip()
                        note = match.group(2).strip().split()[0]
                        ects = float(match.group(2).strip().split()[1].replace(",", "."))

                        data.append(Course(current_section, kurs, note, ects))
                        ects_sum += ects

                        if current_section != "A5":
                            ects_sum_calc += ects
                            float_grade = float(note.replace(",", "."))
                            grades_weighted_sum += float_grade * ects

        avg_grade = grades_weighted_sum / ects_sum_calc if ects_sum_calc > 0 else 0

        return data, ects_sum, avg_grade, ects_sum_calc

    def calculate_prognosis(self, ects_sum, avg_grade, ects_sum_calc):
        target_grades = [1.0, 1.3, 1.7, 2.0, 2.3, 2.7, 3.0, 3.3, 3.7, 4.0]
        total_ects_needed = 180
        remaining_ects = total_ects_needed - ects_sum

        prognosis_text = f"Aktuelle ECTS: {ects_sum:.1f}\nVerbleibende ECTS: {remaining_ects:.1f}\n\n"

        for target in target_grades:
            if remaining_ects > 0:
                needed_grade = (target * total_ects_needed - avg_grade * ects_sum_calc) / remaining_ects
                needed_grade = max(1.0, min(4.0, needed_grade))
                prognosis_text += f"Für Endnote {target:.1f} brauchst du Schnitt: {needed_grade:.2f}\n"

        self.prognose_text.delete(1.0, tk.END)
        self.prognose_text.insert(tk.END, prognosis_text)

    def plot_grade_distribution(self, data):
        grades = [course.note for course in data]
        grade_counts = Counter(grades)

        sorted_grades = sorted(grade_counts.items(), key=lambda x: float(x[0].replace(',', '.')))
        sorted_keys, sorted_values = zip(*sorted_grades)

        fig, ax = plt.subplots()
        ax.bar(sorted_keys, sorted_values)
        ax.set_xlabel("Note")
        ax.set_ylabel("Anzahl")
        ax.set_title("Notenverteilung")

        for widget in self.graph_frame.winfo_children():
            widget.destroy()

        canvas = FigureCanvasTkAgg(fig, master=self.graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFParserApp(root)
    root.mainloop()
