# RadioSim — Signal Flowcharts

## Audio Pipeline Flow

```mermaid
flowchart TD
    A[Audio Source] -->|raw PCM float32| B{Mode Type}
    B -->|FM| C[FM Chain]
    B -->|AM| D[AM Chain]
    B -->|AMHD| E[AMHD Chain]
    B -->|FMHD| F[FMHD Chain]
    B -->|DAB| G[DAB Chain]

    C --> H[SignalSimulator]
    D --> H
    E --> H
    F --> H
    G --> H

    H -->|degraded audio| I[Ring Buffer]
    I -->|pop_chunk| J[PyAudio Callback]
    J -->|int16| K[Speakers]
```

## FM Processing Chain

```mermaid
flowchart LR
    A[Stereo PCM] --> B[Stereo Blend<br/>RSSI → mono]
    B --> C[Bandpass<br/>50Hz – 15kHz]
    C --> D[75µs De-emphasis]
    D --> E[Multipath<br/>delayed copies]
    E --> F[White Noise Floor]
    F --> G[Output]
```

## AM Processing Chain

```mermaid
flowchart LR
    A[Stereo PCM] --> B[Mono Downmix<br/>L+R / 2]
    B --> C[Bandpass<br/>50Hz – 5kHz]
    C --> D[Pink + White Static]
    D --> E[Impulsive Crackle<br/>Poisson events]
    E --> F[Ionospheric Fading<br/>slow AM envelope]
    F --> G[Output]
```

## AMHD Hybrid Chain

```mermaid
flowchart TD
    A[Stereo PCM] --> B{Split}
    B -->|Digital Path| C[Wide BP<br/>50Hz – 15kHz]
    C --> D[Quantization Noise]
    D --> E[Frame Drops<br/>if RSSI weak]
    B -->|Analog Path| F[Mono Downmix]
    F --> G[Narrow BP<br/>50Hz – 5kHz]
    G --> H[Reduced Static]
    E --> I{Crossfade<br/>by RSSI}
    H --> I
    I --> J[Output]
```

## FMHD Hybrid Chain

```mermaid
flowchart TD
    A[Stereo PCM] --> B{Split}
    B -->|Digital Path| C[Flat BP<br/>20Hz – 20kHz]
    C --> D[Subchannel Quality<br/>bitrate sim]
    D --> E[Minimal Noise]
    E --> F[Rare Glitches]
    B -->|Analog Path| G[FM BP<br/>50Hz – 15kHz]
    G --> H[De-emphasis]
    H --> I[FM Noise Floor]
    F --> J{Crossfade<br/>by RSSI}
    I --> J
    J --> K[Output]
```

## DAB+ Processing Chain

```mermaid
flowchart TD
    A[Stereo PCM] --> B[Flat BP<br/>20Hz – 20kHz]
    B --> C{HE-AAC Artifacts<br/>by bitrate}
    C -->|Low bitrate| D[SBR Simulation<br/>HF roll-off + noise]
    C -->|High bitrate| E[Transparent]
    D --> F[Cliff Effect<br/>Burst Errors]
    E --> F
    F -->|RSSI > -80| G[Perfect Output]
    F -->|RSSI < -80| H[Muted / Glitched Output]
```

## Tuning State Machine

```mermaid
stateDiagram-v2
    [*] --> FM: default
    FM --> AM: M key / Tab
    AM --> AMHD: M key / Tab
    AMHD --> FMHD: M key / Tab
    FMHD --> DAB: M key / Tab
    DAB --> FM: M key / Tab

    state FM {
        [*] --> Tuned
        Tuned --> Tuned: ← → adjust 0.1 MHz
    }
    state AM {
        [*] --> Tuned
        Tuned --> Tuned: ← → adjust 1 kHz
    }
    state AMHD {
        [*] --> Tuned
        Tuned --> Tuned: ← → adjust 1 kHz
    }
    state FMHD {
        [*] --> Tuned
        Tuned --> Tuned: ← → adjust 0.1 MHz
    }
    state DAB {
        [*] --> Tuned
        Tuned --> Tuned: ← → adjust 0.1 MHz
    }
```

## Source Lifecycle

```mermaid
flowchart TD
    A[User provides URI] --> B{URI type}
    B -->|Path| C[MP3Source]
    B -->|URL| D[YouTubeSource]

    C --> E[Recursive scan<br/>*.mp3, *.wav, ...]
    E --> F[Build playlist]
    F --> G[Shuffle if enabled]

    D --> H[yt-dlp -j URL<br/>fetch metadata]
    H --> I[yt-dlp -f bestaudio -o - URL<br/>+ ffmpeg pipe]
    I --> J[Raw PCM on stdout]

    G --> K[read_chunk loop]
    J --> K
    K --> L{EOF?}
    L -->|Yes| M{More tracks?}
    M -->|Yes MP3| N[Load next file]
    N --> K
    M -->|Yes YT| O[Loop same track]
    O --> K
    M -->|No| P[Silence / Stop]
    L -->|No| K
```

## RSSI → Noise Mapping

```mermaid
flowchart LR
    subgraph RSSI Levels
        A[-30 dBm<br/>Excellent] --> B[-45 dBm<br/>Very Good]
        B --> C[-60 dBm<br/>Fair]
        C --> D[-75 dBm<br/>Weak]
        D --> E[-90 dBm<br/>Threshold]
        E --> F[-100 dBm<br/>Noise Floor]
    end

    subgraph Effects
        A2[Near-zero noise<br/>Pristine audio]
        B2[Barely audible hiss<br/>Clean audio]
        C2[Noticeable noise<br/>Occasional crackle]
        D2[Strong noise<br/>Fading dips]
        E2[Noise dominates<br/>Barely intelligible]
        F2[Pure noise<br/>Unusable]
    end

    A --> A2
    B --> B2
    C --> C2
    D --> D2
    E --> E2
    F --> F2
```
