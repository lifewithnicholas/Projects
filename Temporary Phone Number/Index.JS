const express = require('express');
const twilio = require('twilio');
const bodyParser = require('body-parser');
const admin = require('firebase-admin');
const dotenv = require('dotenv');

dotenv.config();

// Initialize Firebase Admin SDK
admin.initializeApp({
  credential: admin.credential.cert(require(process.env.FIREBASE_ADMIN_SDK)),
});

const app = express();
app.use(bodyParser.urlencoded({ extended: false }));
app.use(bodyParser.json());

const client = twilio(process.env.TWILIO_ACCOUNT_SID, process.env.TWILIO_AUTH_TOKEN);

// Endpoint to create temporary phone number
app.post('/create-temp-number', async (req, res) => {
  try {
    const { userId, expiryInHours } = req.body;

    // Generate temporary phone number (this can be any available Twilio number)
    const tempNumber = await client.incomingPhoneNumbers
      .create({
        phoneNumber: process.env.TWILIO_PHONE_NUMBER,  // Placeholder: Use your own logic to get available Twilio number
      });

    // Store this number in Firebase DB with expiration time
    const expirationTime = Date.now() + expiryInHours * 60 * 60 * 1000;  // Expiry time in milliseconds
    await admin.firestore().collection('temporary_numbers').doc(userId).set({
      tempNumber: tempNumber.phoneNumber,
      expirationTime: expirationTime,
      receivedMessages: [],
      receivedCalls: [],
    });

    res.status(200).json({ tempNumber: tempNumber.phoneNumber });
  } catch (error) {
    console.error('Error creating temporary number:', error);
    res.status(500).json({ message: 'Failed to create temporary number' });
  }
});

// Webhook for receiving SMS
app.post('/receive-sms', (req, res) => {
  const { From, To, Body } = req.body;

  // Logic to find user based on temp number
  admin.firestore().collection('temporary_numbers')
    .where('tempNumber', '==', To)
    .get()
    .then(snapshot => {
      snapshot.forEach(doc => {
        // Store incoming message
        const userId = doc.id;
        const newMessage = { From, Body, timestamp: Date.now() };
        admin.firestore().collection('temporary_numbers').doc(userId)
          .update({
            receivedMessages: admin.firestore.FieldValue.arrayUnion(newMessage),
          });

        // Notify user via Firebase
        admin.messaging().sendToTopic(userId, {
          notification: {
            title: 'New Message',
            body: `You received a message from ${From}: ${Body}`,
          },
        });
      });
    })
    .catch(error => {
      console.error('Error handling SMS:', error);
    });

  res.status(200).send('<Response></Response>');
});

// Webhook for receiving calls
app.post('/receive-call', (req, res) => {
  const { From, To } = req.body;

  // Handle incoming call logic
  admin.firestore().collection('temporary_numbers')
    .where('tempNumber', '==', To)
    .get()
    .then(snapshot => {
      snapshot.forEach(doc => {
        const userId = doc.id;
        // Record call or forward as per logic
        const newCall = { From, timestamp: Date.now() };
        admin.firestore().collection('temporary_numbers').doc(userId)
          .update({
            receivedCalls: admin.firestore.FieldValue.arrayUnion(newCall),
          });

        // Notify user via Firebase
        admin.messaging().sendToTopic(userId, {
          notification: {
            title: 'Incoming Call',
            body: `You received a call from ${From}`,
          },
        });
      });
    })
    .catch(error => {
      console.error('Error handling call:', error);
    });

  // Respond with a message or call-forwarding instructions
  res.status(200).send('<Response><Say>Thanks for calling!</Say></Response>');
});

// Start the server
const port = process.env.PORT || 5000;
app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
