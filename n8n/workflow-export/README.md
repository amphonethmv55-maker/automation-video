# n8n Workflow Exports

เก็บไฟล์ JSON ที่ export จาก n8n และผ่านการทดสอบแล้วในโฟลเดอร์นี้ เพื่อให้ workflow ถูก version control ผ่าน GitHub

แนวทางการตั้งชื่อ:

```text
automation-video-main.json
automation-video-test.json
```

ก่อน commit ต้องตรวจว่าไฟล์ export ไม่มี credentials, access tokens, passwords หรือข้อมูล execution ที่เป็นความลับ

ลำดับการนำ workflow ขึ้น Production:

1. สร้างหรือแก้ workflow บน Development n8n (`192.168.126.128:5678`)
2. ทดสอบ workflow ให้ผ่าน
3. Export workflow เป็น JSON ลงโฟลเดอร์นี้
4. Commit และ push เข้า branch `develop`
5. Review และ merge เข้า `main`
6. Pull `main` บน Production Server
7. Import JSON เข้า Production n8n (`192.168.20.193:5678`)

