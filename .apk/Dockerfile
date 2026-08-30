# Srodowisko budowania APK.
#
# Na komputerze nie ma ani Javy, ani Node, ani Android SDK - i nie musi byc.
# Caly zestaw narzedzi siedzi tutaj, tak jak reszta projektu siedzi w Dockerze.
#
# Obraz wazy ok. 3 GB, bo Android SDK swoje wazy. Pierwsze budowanie trwa
# kilkanascie minut; kolejne korzystaja z wolumenow na cache Gradle i npm,
# wiec schodza do okolo dwoch minut.

FROM eclipse-temurin:21-jdk-jammy

# Wersje przypiete swiadomie. Capacitor 7 wymaga Node 20+, JDK 21 i SDK 35 -
# rozjazd ktorejkolwiek z tych trzech rzeczy konczy sie bledem w polowie
# budowania, wiec nie bierzemy "najnowszych".
ENV ANDROID_SDK_ROOT=/opt/android-sdk \
    ANDROID_HOME=/opt/android-sdk \
    WERSJA_NARZEDZI=11076708 \
    POZIOM_API=35 \
    BUILD_TOOLS=35.0.0 \
    DEBIAN_FRONTEND=noninteractive \
    GRADLE_USER_HOME=/cache/gradle \
    npm_config_cache=/cache/npm

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl unzip git ca-certificates zip \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Android SDK z wiersza polecen - bez Android Studio.
RUN mkdir -p "${ANDROID_SDK_ROOT}/cmdline-tools" \
    && curl -fsSL -o /tmp/narzedzia.zip \
        "https://dl.google.com/android/repository/commandlinetools-linux-${WERSJA_NARZEDZI}_latest.zip" \
    && unzip -q /tmp/narzedzia.zip -d "${ANDROID_SDK_ROOT}/cmdline-tools" \
    && mv "${ANDROID_SDK_ROOT}/cmdline-tools/cmdline-tools" "${ANDROID_SDK_ROOT}/cmdline-tools/latest" \
    && rm /tmp/narzedzia.zip

ENV PATH="${ANDROID_SDK_ROOT}/cmdline-tools/latest/bin:${ANDROID_SDK_ROOT}/platform-tools:${ANDROID_SDK_ROOT}/build-tools/${BUILD_TOOLS}:${PATH}"

# Licencje trzeba zaakceptowac, inaczej sdkmanager niczego nie pobierze.
RUN yes | sdkmanager --licenses > /dev/null \
    && sdkmanager --install \
        "platform-tools" \
        "platforms;android-${POZIOM_API}" \
        "build-tools;${BUILD_TOOLS}" \
    > /dev/null

WORKDIR /projekt

# Skrypt budowania jest osobnym plikiem, zeby dalo sie go czytac i poprawiac
# bez przebudowywania calego obrazu.
COPY zbuduj.sh /usr/local/bin/zbuduj
# Pliki powstaja na Windows, wiec moga miec CRLF. Bash z takim koncem linii
# wywala sie komunikatem o nieistniejacym katalogu, ktory niczego nie tlumaczy.
RUN sed -i 's/\r$//' /usr/local/bin/zbuduj && chmod +x /usr/local/bin/zbuduj

CMD ["zbuduj"]
