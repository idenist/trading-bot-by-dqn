module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    plugins: [
      'expo-router/babel',           // expo-router (기존)
      'react-native-reanimated/plugin',  // reanimated (추가, 반드시 마지막!)
    ],
  };
};
