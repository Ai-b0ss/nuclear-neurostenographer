#include <QAudioFormat>
#include <QAudioInput>
#include <QAudioSource>
#include <QApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileDialog>
#include <QMediaDevices>
#include <QMessageBox>
#include <QPushButton>
#include <QTextEdit>
#include <QVBoxLayout>
#include <QWidget>

class MainWindow final : public QWidget {
public:
    MainWindow() {
        setWindowTitle(QStringLiteral("Нейро-стенографист · офлайн"));
        resize(720, 520);
        auto *layout = new QVBoxLayout(this);
        auto *record = new QPushButton(QStringLiteral("Записать разговор"));
        auto *import = new QPushButton(QStringLiteral("Импортировать аудио"));
        auto *exportButton = new QPushButton(QStringLiteral("Экспортировать TXT"));
        transcript = new QTextEdit;
        transcript->setReadOnly(true);
        transcript->setPlaceholderText(QStringLiteral("Здесь появится стенограмма. Распознавание речи пока не подключено."));
        layout->addWidget(record);
        layout->addWidget(import);
        layout->addWidget(exportButton);
        layout->addWidget(transcript, 1);
        connect(record, &QPushButton::clicked, this, [this, record] { toggleRecording(record); });
        connect(import, &QPushButton::clicked, this, [this] {
            const auto path = QFileDialog::getOpenFileName(this, QStringLiteral("Выбрать аудио"), {},
                QStringLiteral("Аудио (*.wav *.mp3 *.m4a *.ogg);;Все файлы (*)"));
            if (!path.isEmpty()) { audioPath = path; transcript->setPlaceholderText(QStringLiteral("Выбран файл: ") + path + QStringLiteral("\nРаспознавание пока недоступно.")); }
        });
        connect(exportButton, &QPushButton::clicked, this, [this] {
            const auto path = QFileDialog::getSaveFileName(this, QStringLiteral("Экспорт стенограммы"),
                QStringLiteral("transcript.txt"), QStringLiteral("Текст (*.txt)"));
            if (path.isEmpty()) return;
            QFile file(path);
            if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) { QMessageBox::warning(this, QStringLiteral("Ошибка"), file.errorString()); return; }
            file.write(transcript->toPlainText().toUtf8());
        });
    }
private:
    QTextEdit *transcript{};
    QString audioPath;
    QAudioSource *source{};
    QFile recording;

    void toggleRecording(QPushButton *button) {
        if (source) {
            source->stop();
            recording.close();
            source->deleteLater();
            source = nullptr;
            button->setText(QStringLiteral("Записать разговор"));
            QMessageBox::information(this, QStringLiteral("Запись сохранена"), recording.fileName());
            return;
        }
        const auto device = QMediaDevices::defaultAudioInput();
        if (device.isNull()) { QMessageBox::warning(this, QStringLiteral("Микрофон недоступен"), QStringLiteral("Подключите микрофон и повторите.")); return; }
        audioPath = QDir::temp().filePath(QStringLiteral("recording-%1.pcm").arg(QDateTime::currentMSecsSinceEpoch()));
        recording.setFileName(audioPath);
        if (!recording.open(QIODevice::WriteOnly)) { QMessageBox::warning(this, QStringLiteral("Ошибка"), recording.errorString()); return; }
        QAudioFormat format;
        format.setSampleRate(16000); format.setChannelCount(1); format.setSampleFormat(QAudioFormat::Int16);
        source = new QAudioSource(device, format, this);
        auto *input = source->start();
        if (!input) { source->deleteLater(); source = nullptr; recording.close(); QMessageBox::warning(this, QStringLiteral("Ошибка"), QStringLiteral("Не удалось начать запись.")); return; }
        connect(input, &QIODevice::readyRead, this, [this, input] { recording.write(input->readAll()); });
        button->setText(QStringLiteral("Остановить запись"));
        transcript->setPlaceholderText(QStringLiteral("Идёт локальная запись PCM 16 кГц. Распознавание пока не подключено."));
    }
};

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    MainWindow window;
    window.show();
    return app.exec();
}
