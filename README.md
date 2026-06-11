# 🛒 Automated Smart Shopping Cart
**IoT-Powered Self-Billing & Anti-Theft Retail Solution**

<p align="center">
  <em>A modular smart cart system designed to eliminate checkout queues, automate billing, and secure retail transactions using computer vision and weight validation.</em>
</p>

---

## 📖 Abstract
The Automated Smart Shopping Cart introduces a self-billing module for modern retail stores. It automates product scanning and instant billing, allowing customers to bypass traditional long queues. To prevent theft and ensure inventory accuracy, the system employs a real-time weight validation mechanism—verifying that the physical item placed in the cart matches the digital weight profile of the scanned barcode. 

Powered by a Raspberry Pi 4, load cells, computer vision, and a cloud-synchronized touchscreen GUI, this project delivers a cost-effective, scalable, and customer-friendly retail experience.

---

## ✨ Key Features & Overview
* 🚀 **Queue-Free Checkout:** Instant, automated product scanning and billing directly at the cart.
* ⚖️ **Anti-Theft Weight Validation:** A load cell continuously monitors the cart's payload. The system cross-references the scanned item's expected weight with the actual weight added, confirming every scanned product is genuinely placed in the cart.
* 💳 **Secure User Authentication:** Login sessions protected by Email OTPs managed via Supabase.
* 🔄 **Real-Time Cloud Sync:** Instant dynamic data retrieval and inventory updates.
* 📱 **Omnichannel Access:** Features both an on-cart local GUI and a responsive web application for extended accessibility.
* 🧩 **Modular Design:** Highly scalable and easy to integrate into existing modern retail infrastructure.

---

## 🛠️ Hardware & Architecture

### Hardware Components
* **Compute:** Raspberry Pi 4
* **Weighing Mechanism:** Load Cell with HX711 Amplifier
* **Display:** Touchscreen Interface
* **Vision System:** Raspberry Pi Camera Module 
  > **Hardware Design Note:** The camera is specifically positioned *below* the main screen to provide an ergonomic, natural scanning angle for users while protecting the lens.

### Software Stack
* **Database & Auth:** Supabase (PostgreSQL)
* **Computer Vision:** OpenCV and pyzbar (for real-time barcode identification)
* **Frontend / GUI:** Python-based GUI (on-cart) & Responsive Web Application
* **Payments:** Razorpay API Integration

---

## 📈 Current Status & Milestones

### 🗄️ Database & Infrastructure
* **Architecture Evolution:** Successfully transitioned from a local SQLite database to a cloud-based Supabase (PostgreSQL) environment to enable real-time data synchronization and multi-cart scalability.
* **Inventory Management:** Designed and implemented a comprehensive database schema tracking stock levels, product categories, and supplier details.

### 🖥️ User Interface & Web Development
* **Core GUI:** Completed the Python-based Graphical User Interface featuring a main dashboard and secondary pages for seamless, touch-friendly user interaction.
* **Web Expansion:** Developed a responsive Web Application, extending the system's accessibility from local hardware to browser-based devices.

### ⚙️ Functionality & Integration
* **Automated Identification:** Implemented barcode scanning functionality using computer vision libraries, enabling the system to instantly fetch and display product details.
* **Real-Time Integration:** Achieved full synchronization between the GUI and the Supabase backend for dynamic data retrieval during user interactions.

### 🔒 Security & User Management
* **Authentication:** Integrated a secure login system using Email OTPs via Supabase to manage user sessions and protect shopping data.
* **Personalization Base:** Established the foundation for tracking individual shopping histories and maintaining personalized cart settings.

---

## 🔮 Future Enhancements
* **Advanced Object Detection:** Integrating YOLO-based object detection to visually verify the item matches the weight profile, creating a foolproof dual-verification system.
* **AI Personalization:** Implementing machine learning capabilities to analyze shopping patterns and provide hyper-relevant product suggestions.
* **Seamless Payments:** Expanding digital checkout options to include contactless and biometric authorization for entirely frictionless payments.
* **AR Engagement:** Adding interactive product highlights and contextual prompts to the display for faster item discovery in the aisles.

---

## 👨‍💻 Developer
Developed as a final year B.Tech Computer Science Engineering main project.
