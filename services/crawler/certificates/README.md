# 우리WON 서버의 누락 중간 인증서

`www.wooriwonmobile.com`은 2026-10-25 조사 시 리프 인증서만 전송했다.
`WonCrawler`의 개별 SSL 컨텍스트에 누락된 중간 인증서를 제공한다.
시스템의 기존 루트 CA, 호스트 이름, 유효기간 검증을 그대로 사용한다.
인증서 검증 비활성화 또는 PARTIAL_CHAIN 플래그를 사용하지 않는다.

- 발급기관 배포 원본: https://cacerts.digicert.com/GeoTrustEVRSACAG2.crt
- Subject: GeoTrust EV RSA CA G2
- Issuer: DigiCert Global Root G2
- 유효기간: 2020-07-02 ~ 2030-07-02
- SHA-256: `2D140F20B8A96E2B4D2F1CC5ACA5E5A1E7DC56A7491E510906960F38D2D21AEF`
- 기존 OS 루트 검증: `openssl verify services/crawler/certificates/geotrust-ev-rsa-ca-g2.pem`

서버가 인증서를 갱신해 체인이 달라지는 경우 검증 실패로 보고하고 발급기관 원본을 재검증한다.
