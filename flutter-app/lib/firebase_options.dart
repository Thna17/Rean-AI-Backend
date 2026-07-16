// File: firebase_options.dart.example
// This is a template file. Copy to firebase_options.dart and replace with your Firebase config.
//
// To get your Firebase configuration:
// 1. Go to Firebase Console: https://console.firebase.google.com/
// 2. Select your project
// 3. Go to Project Settings > General
// 4. Scroll down to "Your apps" section
// 5. Click on the Flutter app
// 6. Copy the configuration values
//
// OR run: flutterfire configure

import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, kIsWeb, TargetPlatform;

class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    if (kIsWeb) {
      return web;
    }
    switch (defaultTargetPlatform) {
      case TargetPlatform.android:
        return android;
      case TargetPlatform.iOS:
        return ios;
      case TargetPlatform.macOS:
        return macos;
      case TargetPlatform.windows:
        return windows;
      case TargetPlatform.linux:
        throw UnsupportedError(
          'DefaultFirebaseOptions have not been configured for linux - '
          'you can reconfigure this by running the FlutterFire CLI again.',
        );
      default:
        throw UnsupportedError(
          'DefaultFirebaseOptions are not supported for this platform.',
        );
    }
  }

  static const FirebaseOptions web = FirebaseOptions(
    apiKey: 'AIzaSyDSiAAi92JuGzUZe_bAUVkGFdX-rekhcjk',
    appId: '1:759793755680:web:3dfb426429011d99e7be45',
    messagingSenderId: '759793755680',
    projectId: 'ai-tutor-26fe2',
    authDomain: 'ai-tutor-26fe2.firebaseapp.com',
    storageBucket: 'ai-tutor-26fe2.firebasestorage.app',
    measurementId: 'G-RBW5V82FBP',
  );

  static const FirebaseOptions android = FirebaseOptions(
    apiKey: 'AIzaSyDUm-tTWvrIIv72bFSOFmARDWgXHE2VN0Y',
    appId: '1:759793755680:android:71142c632c565438e7be45',
    messagingSenderId: '759793755680',
    projectId: 'ai-tutor-26fe2',
    storageBucket: 'ai-tutor-26fe2.firebasestorage.app',
  );

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'AIzaSyBy2Vqu6-BHVBThwTLy_vFUV9Bu0PrUsaQ',
    appId: '1:759793755680:ios:9299fbe9d90ec2fde7be45',
    messagingSenderId: '759793755680',
    projectId: 'ai-tutor-26fe2',
    storageBucket: 'ai-tutor-26fe2.firebasestorage.app',
    iosBundleId: 'com.nhthang.lexilingoApp',
  );

  static const FirebaseOptions macos = FirebaseOptions(
    apiKey: 'AIzaSyBy2Vqu6-BHVBThwTLy_vFUV9Bu0PrUsaQ',
    appId: '1:759793755680:ios:5a4a0529cdeba2f3e7be45',
    messagingSenderId: '759793755680',
    projectId: 'ai-tutor-26fe2',
    storageBucket: 'ai-tutor-26fe2.firebasestorage.app',
    iosBundleId: 'com.lexilingo.lexilingoApp',
  );

  static const FirebaseOptions windows = FirebaseOptions(
    apiKey: 'AIzaSyDSiAAi92JuGzUZe_bAUVkGFdX-rekhcjk',
    appId: '1:759793755680:web:4e1ddc8828dd0ab4e7be45',
    messagingSenderId: '759793755680',
    projectId: 'ai-tutor-26fe2',
    authDomain: 'ai-tutor-26fe2.firebaseapp.com',
    storageBucket: 'ai-tutor-26fe2.firebasestorage.app',
    measurementId: 'G-NW84K2T8Y5',
  );
}
