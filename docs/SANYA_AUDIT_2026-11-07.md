# Published work by Fancyhe1 and reported work on 6–7 November

Read-only audit of `Ai-b0ss/nuclear-neurostenographer`, main `b979f49`.

## Published implementation

`cpp/honor-local-performance` ends at `78ac205` (5 November, 06:38 Moscow).
`cpp/native-core` ends at `543fc77` (4 November, 18:10 Moscow).
These branches are separate from current main and have no merged product PR.

- C++ Nemotron frontend, speaker cache, ONNX session and chunk orchestration.
- Opt-in C++ sherpa ASR session, window decoding and cancellation/lifecycle checks.
- Android 16/API 36, x86_64, 4 GiB/16 KiB emulator checks and both-ABI alignment checks.
- C++/JNI parity on the frozen cases. This is not evidence of an ASR speedup.
- Several ASR heads, multilingual CTC, boundary/window policies and external Russian corpora were measured.
- A natural 20-minute DataHive recording completed through the old CTC product path on the emulator. No manually verified transcript was available; no natural WER/DER claim follows.
- MOSS Q4 ran in a standalone Android C++ process. On i1321 its tuned run took 33.43 s versus 1.539 s for A0. The tiny two-file comparison did not justify promotion.
- Qt toolchain smoke builds exist for both ABIs; this is not a complete Qt transcription application.

Important naming mismatch: the branch calls the **plain** GigaAM RNN-T conversion from csukuangfj A3. Current main's A3 is the **e2e** RNN-T conversion from Smirnov75. Its A3 comparisons must not be presented as a regression test of current product A3.

## Work reported on 6–7 November

| 7 ноября, Москва | Что подтверждается перепиской |
|---|---|
| 12:23 | Сел смотреть код и тестировать приложение; NPU планировал изучить позже |
| 15:36; 17:45 | Кратко изучил распространённость NPU, затем продолжил проверку |
| 19:17; 20:42 | Сообщил о проблеме с WAV, которую считал отличной от уже исправленной владельцем; воспроизведение не описал |
| 20:42; 20:59 | У него нет NPU; работоспособность реализации не подтверждена, обычный эмулятор аппаратный чип не заменяет |

Это позволяет говорить о проверке приложения и исследовании NPU. Готовое ускорение, законченный аудит или второй исправленный WAV-баг из этой переписки не следуют.

The supplied team correspondence reports code review, application testing, another WAV issue and NPU investigation. It explicitly says the author had no NPU hardware and could not establish that the NPU path works.

At audit time, no matching new commit, PR, NPU/NNAPI implementation or second WAV patch was found in the accessible remote refs, commit search or the owner's local Git history. The publicly searchable account repositories also did not reveal a transcription fork. A missing accessible artifact does not prove that local work was not done.

Therefore:

- NPU investigation: **reported, no measured acceleration or accessible implementation established**.
- WAV issue: **reported, exact failure and patch not available**; do not equate it with the owner's earlier import fix.
- Code audit: **reported**, no accessible written findings or new patch established.
- Do not attribute main's UI, live latency, WAV feedback fix or contest JSON work to Fancyhe1 on the basis of these messages.

Useful next evidence is the actual branch/commit or patch, exact WAV reproducer and NPU provider/model configuration. No messages were sent to teammates during this audit.

## Source links

- [C++ performance branch](https://github.com/Ai-b0ss/nuclear-neurostenographer/tree/cpp/honor-local-performance), frozen head [78ac205](https://github.com/Ai-b0ss/nuclear-neurostenographer/commit/78ac20519e15785208743fce8880f81bc3daddd7).
- [Native core branch](https://github.com/Ai-b0ss/nuclear-neurostenographer/tree/cpp/native-core), frozen head [543fc77](https://github.com/Ai-b0ss/nuclear-neurostenographer/commit/543fc77a0dac5383c78a94df965442677572101c).
- The 6–7 November activity is established only by the correspondence supplied by the owner; it is not a GitHub artifact. Available remote refs were checked again before saving this report.
